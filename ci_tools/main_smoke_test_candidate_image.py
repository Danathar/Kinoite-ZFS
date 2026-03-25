"""
Script: ci_tools/main_smoke_test_candidate_image.py
What: Runs a lightweight post-build validation against the published candidate image.
Doing: Resolves the candidate digest, pulls the image locally, checks that ZFS userland is installed, and verifies a ZFS module payload exists for every kernel shipped in the image.
Why: Candidate compose success alone does not prove the published image still carries the expected module files.
Goal: Fail before promotion when the candidate image is missing its ZFS payload.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from ci_tools.common import (
    CiToolError,
    load_layer_files_from_oci_layout,
    normalize_owner,
    require_env,
    skopeo_inspect_digest,
    skopeo_copy,
    sort_kernel_releases,
    unpack_layer_tarballs,
)


def candidate_image_tag_ref(
    image_org: str,
    image_name: str,
    fedora_version: str,
    sha_short: str,
) -> str:
    """Return the candidate tag ref produced by the publish workflow."""

    return f"docker://ghcr.io/{image_org}/{image_name}:{sha_short}-{fedora_version}"


def candidate_image_digest_ref(image_org: str, image_name: str, digest: str) -> str:
    """Return the digest-pinned candidate ref used by Podman for smoke checks."""

    return f"ghcr.io/{image_org}/{image_name}@{digest}"


def _image_kernel_releases(rootfs_dir: Path) -> list[str]:
    modules_root = rootfs_dir / "lib" / "modules"
    if not modules_root.exists():
        return []
    return sort_kernel_releases(
        [entry.name for entry in modules_root.iterdir() if entry.is_dir()]
    )


def smoke_test_candidate_image(
    *,
    image_org: str,
    image_name: str,
    fedora_version: str,
    git_sha: str,
    registry_actor: str,
    registry_token: str,
    digest_lookup: Callable[..., str] = skopeo_inspect_digest,
    image_copier: Callable[..., None] = skopeo_copy,
    layer_loader: Callable[[Path], list[Path]] = load_layer_files_from_oci_layout,
    layer_unpacker: Callable[[list[Path], Path], None] = unpack_layer_tarballs,
) -> str:
    """
    Validate the published candidate image, then return its digest-pinned ref.

    This check intentionally stays lightweight:
    - resolve the exact candidate digest from the published tag
    - verify ZFS userspace packages/commands exist
    - verify every shipped kernel directory has a ZFS module payload
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
        rootfs_dir = root / "rootfs"
        rootfs_dir.mkdir(parents=True, exist_ok=True)

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
        layer_unpacker(layer_files, rootfs_dir)

        kernel_releases = _image_kernel_releases(rootfs_dir)
        if not kernel_releases:
            raise CiToolError(f"No kernel directories found in candidate image {candidate_ref}")

        # Confirm the userland side is present too, not just stray module files.
        for command_name in ("zfs", "zpool"):
            command_paths = [
                rootfs_dir / "usr" / "sbin" / command_name,
                rootfs_dir / "usr" / "bin" / command_name,
            ]
            if not any(path.is_file() for path in command_paths):
                raise CiToolError(
                    f"Candidate image {candidate_ref} is missing expected command {command_name}"
                )

        for kernel_release in kernel_releases:
            module_dir = rootfs_dir / "lib" / "modules" / kernel_release / "extra" / "zfs"
            if not module_dir.exists() or not any(module_dir.glob("zfs.ko*")):
                raise CiToolError(
                    "Candidate image is missing a ZFS module payload for kernel "
                    f"{kernel_release}: {candidate_ref}"
                )

    print(f"Candidate image smoke test passed: {candidate_ref}")
    print(f"Kernels with ZFS payloads: {' '.join(kernel_releases)}")
    return candidate_ref


def main() -> None:
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    image_name = require_env("CANDIDATE_IMAGE_NAME")
    fedora_version = require_env("FEDORA_VERSION")
    registry_actor = require_env("REGISTRY_ACTOR")
    registry_token = require_env("REGISTRY_TOKEN")
    git_sha = require_env("GITHUB_SHA")

    smoke_test_candidate_image(
        image_org=image_org,
        image_name=image_name,
        fedora_version=fedora_version,
        git_sha=git_sha,
        registry_actor=registry_actor,
        registry_token=registry_token,
    )


if __name__ == "__main__":
    main()
