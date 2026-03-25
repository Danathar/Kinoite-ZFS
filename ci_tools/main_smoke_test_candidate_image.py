"""
Script: ci_tools/main_smoke_test_candidate_image.py
What: Runs a lightweight post-build validation against the published candidate image.
Doing: Resolves the candidate digest, pulls the image locally, checks that ZFS userland is installed, and verifies a ZFS module payload exists for every kernel shipped in the image.
Why: Candidate compose success alone does not prove the published image still carries the expected module files.
Goal: Fail before promotion when the candidate image is missing its ZFS payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
from pathlib import PurePosixPath
from tempfile import TemporaryDirectory
import re
import tarfile

from ci_tools.common import (
    CiToolError,
    kernel_releases_from_env,
    load_layer_files_from_oci_layout,
    normalize_owner,
    optional_env,
    require_env,
    skopeo_inspect_digest,
    skopeo_copy,
    sort_kernel_releases,
    write_github_outputs,
)

MODULE_PATH_RE = re.compile(r"^(?:usr/)?lib/modules/([^/]+)/extra/zfs/(zfs\.ko(?:\..+)?)$")
COMMAND_PATHS = {
    "usr/sbin/zfs": "zfs",
    "usr/bin/zfs": "zfs",
    "usr/sbin/zpool": "zpool",
    "usr/bin/zpool": "zpool",
}


@dataclass(frozen=True)
class CandidateImageLayerScanResult:
    """Small summary of the final candidate image paths we care about."""

    kernel_releases: tuple[str, ...]
    command_names: tuple[str, ...]


@dataclass(frozen=True)
class CandidateImageSmokeTestResult:
    """Result returned after the candidate smoke test succeeds."""

    candidate_ref: str
    candidate_digest: str
    kernel_releases: tuple[str, ...]


def candidate_image_tag_ref(
    image_org: str,
    image_name: str,
    fedora_version: str,
    sha_short: str,
) -> str:
    """Return the candidate tag ref produced by the publish workflow."""

    return f"docker://ghcr.io/{image_org}/{image_name}:{sha_short}-{fedora_version}"


def candidate_image_digest_ref(image_org: str, image_name: str, digest: str) -> str:
    """Return the digest-pinned candidate ref used by smoke checks."""

    return f"ghcr.io/{image_org}/{image_name}@{digest}"


def _normalize_tar_member_name(name: str) -> str:
    """Normalize one tar member path for path-based inspection."""

    normalized = name
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return str(PurePosixPath(normalized))


def _apply_whiteout(
    path: str,
    *,
    present_command_paths: set[str],
    present_module_paths: dict[str, set[str]],
) -> bool:
    """
    Apply one OCI whiteout entry to the tracked command/module state.

    Returns `True` when `path` is itself a whiteout entry and should not be
    treated as a normal payload path.
    """

    whiteout_path = PurePosixPath(path)
    whiteout_name = whiteout_path.name

    if whiteout_name == ".wh..wh..opq":
        prefix = f"{whiteout_path.parent}/"
        present_command_paths.difference_update(
            command_path
            for command_path in tuple(present_command_paths)
            if command_path.startswith(prefix)
        )
        for kernel_release, module_paths in present_module_paths.items():
            present_module_paths[kernel_release] = {
                module_path
                for module_path in module_paths
                if not module_path.startswith(prefix)
            }
        return True

    if not whiteout_name.startswith(".wh."):
        return False

    target_path = str(whiteout_path.parent / whiteout_name.removeprefix(".wh."))
    present_command_paths.discard(target_path)

    for kernel_release, module_paths in present_module_paths.items():
        module_paths.discard(target_path)
        present_module_paths[kernel_release] = module_paths

    return True


def inspect_candidate_image_layers(
    layer_files: list[Path],
    *,
    expected_kernel_releases: list[str] | None = None,
) -> CandidateImageLayerScanResult:
    """
    Scan candidate-image layer tarballs for the exact paths the smoke test needs.

    This avoids reconstructing the whole rootfs tree. We only track final-path
    state for:
    - `zfs` / `zpool` command paths
    - `lib/modules/<kernel>/extra/zfs/zfs.ko*` payloads
    """

    present_module_paths: dict[str, set[str]] = {}
    tracked_kernels = set(expected_kernel_releases or [])
    present_command_paths: set[str] = set()

    for layer_file in layer_files:
        with tarfile.open(layer_file, "r") as layer_tar:
            for member in layer_tar:
                path = _normalize_tar_member_name(member.name)
                if path in ("", "."):
                    continue

                if _apply_whiteout(
                    path,
                    present_command_paths=present_command_paths,
                    present_module_paths=present_module_paths,
                ):
                    continue

                if not (member.isfile() or member.islnk() or member.issym()):
                    continue

                command_name = COMMAND_PATHS.get(path)
                if command_name is not None:
                    present_command_paths.add(path)
                    continue

                match = MODULE_PATH_RE.match(path)
                if not match:
                    continue

                kernel_release = match.group(1)
                if tracked_kernels and kernel_release not in tracked_kernels:
                    continue

                present_module_paths.setdefault(kernel_release, set()).add(path)

    kernel_releases = tuple(
        sort_kernel_releases(
            [
                kernel_release
                for kernel_release, module_paths in present_module_paths.items()
                if module_paths
            ]
        )
    )
    return CandidateImageLayerScanResult(
        kernel_releases=kernel_releases,
        command_names=tuple(
            sorted(
                {
                    COMMAND_PATHS[command_path]
                    for command_path in present_command_paths
                }
            )
        ),
    )


def smoke_test_candidate_image(
    *,
    image_org: str,
    image_name: str,
    fedora_version: str,
    git_sha: str,
    registry_actor: str,
    registry_token: str,
    expected_kernel_releases: list[str] | None = None,
    digest_lookup: Callable[..., str] = skopeo_inspect_digest,
    image_copier: Callable[..., None] = skopeo_copy,
    layer_loader: Callable[[Path], list[Path]] = load_layer_files_from_oci_layout,
    layer_inspector: Callable[..., CandidateImageLayerScanResult] = inspect_candidate_image_layers,
) -> CandidateImageSmokeTestResult:
    """
    Validate the published candidate image, then return its digest-pinned ref.

    This check intentionally stays lightweight:
    - resolve the exact candidate digest from the published tag
    - inspect only the layer paths needed for ZFS verification
    - verify ZFS userspace packages/commands exist
    - verify every expected kernel release has a ZFS module payload
    """

    sha_short = git_sha[:7]
    creds = f"{registry_actor}:{registry_token}"
    candidate_tag_ref = candidate_image_tag_ref(
        image_org=image_org,
        image_name=image_name,
        fedora_version=fedora_version,
        sha_short=sha_short,
    )
    candidate_digest = digest_lookup(candidate_tag_ref, creds=creds)
    if not candidate_digest or candidate_digest == "null":
        raise CiToolError(f"Failed to resolve candidate digest for {candidate_tag_ref}")

    candidate_ref = candidate_image_digest_ref(image_org, image_name, candidate_digest)
    with TemporaryDirectory(prefix="candidate-image-smoke-") as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "image"

        image_copier(
            candidate_image_tag_ref(
                image_org=image_org,
                image_name=image_name,
                fedora_version=fedora_version,
                sha_short=sha_short,
            ),
            f"dir:{image_dir}",
            creds=creds,
        )
        layer_files = layer_loader(image_dir)
        inspection = layer_inspector(
            layer_files,
            expected_kernel_releases=expected_kernel_releases,
        )

        # Confirm the userland side is present too, not just stray module files.
        missing_commands = sorted(
            {"zfs", "zpool"} - set(inspection.command_names)
        )
        if missing_commands:
            raise CiToolError(
                f"Candidate image {candidate_ref} is missing expected command {missing_commands[0]}"
            )

        kernel_releases = tuple(expected_kernel_releases or inspection.kernel_releases)
        if not kernel_releases:
            raise CiToolError(
                f"No ZFS kernel payloads found in candidate image {candidate_ref}"
            )

        missing_kernel_releases = [
            kernel_release
            for kernel_release in kernel_releases
            if kernel_release not in inspection.kernel_releases
        ]
        if missing_kernel_releases:
            raise CiToolError(
                "Candidate image is missing a ZFS module payload for kernels "
                f"{' '.join(missing_kernel_releases)}: {candidate_ref}"
            )

    print(f"Candidate image smoke test passed: {candidate_ref}")
    print(f"Kernels with ZFS payloads: {' '.join(kernel_releases)}")
    return CandidateImageSmokeTestResult(
        candidate_ref=candidate_ref,
        candidate_digest=candidate_digest,
        kernel_releases=kernel_releases,
    )


def main() -> None:
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    image_name = require_env("CANDIDATE_IMAGE_NAME")
    fedora_version = require_env("FEDORA_VERSION")
    registry_actor = require_env("REGISTRY_ACTOR")
    registry_token = require_env("REGISTRY_TOKEN")
    git_sha = require_env("GITHUB_SHA")
    expected_kernel_releases = sort_kernel_releases(kernel_releases_from_env())

    result = smoke_test_candidate_image(
        image_org=image_org,
        image_name=image_name,
        fedora_version=fedora_version,
        git_sha=git_sha,
        registry_actor=registry_actor,
        registry_token=registry_token,
        expected_kernel_releases=expected_kernel_releases or None,
    )
    if optional_env("GITHUB_OUTPUT"):
        write_github_outputs(
            {
                "candidate_image_ref": result.candidate_ref,
                "candidate_image_digest": result.candidate_digest,
                "kernel_releases": " ".join(result.kernel_releases),
            }
        )


if __name__ == "__main__":
    main()
