"""
Script: ci_tools/main_smoke_test_candidate_image.py
What: Runs a lightweight post-build validation against the published candidate image.
Doing: Resolves the candidate digest, pulls the image locally, checks that ZFS userland is installed, and verifies a ZFS module payload exists for every kernel shipped in the image.
Why: Candidate compose success alone does not prove the published image still carries the expected module files.
Goal: Fail before promotion when the candidate image is missing its ZFS payload.
"""

from __future__ import annotations

from collections.abc import Callable

from ci_tools.common import (
    CiToolError,
    normalize_owner,
    require_env,
    run_cmd,
    skopeo_inspect_digest,
    sort_kernel_releases,
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


def _podman_shell_args(image_ref: str, shell_command: str) -> list[str]:
    return [
        "podman",
        "run",
        "--rm",
        "--entrypoint",
        "/bin/sh",
        image_ref,
        "-lc",
        shell_command,
    ]


def smoke_test_candidate_image(
    *,
    image_org: str,
    image_name: str,
    fedora_version: str,
    git_sha: str,
    registry_actor: str,
    registry_token: str,
    digest_lookup: Callable[..., str] = skopeo_inspect_digest,
    command_runner: Callable[..., str] = run_cmd,
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
    command_runner(
        ["podman", "pull", "--quiet", "--creds", creds, candidate_ref],
        capture_output=False,
    )

    kernel_output = command_runner(
        _podman_shell_args(
            candidate_ref,
            "find /lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\\n'",
        )
    )
    kernel_releases = sort_kernel_releases(kernel_output.splitlines())
    if not kernel_releases:
        raise CiToolError(f"No kernel directories found in candidate image {candidate_ref}")

    # Confirm the userland side is present too, not just stray module files.
    command_runner(
        _podman_shell_args(
            candidate_ref,
            "rpm -q zfs kmod-zfs >/dev/null && command -v zfs >/dev/null && command -v zpool >/dev/null",
        )
    )

    for kernel_release in kernel_releases:
        command_runner(
            _podman_shell_args(
                candidate_ref,
                "find "
                f"/lib/modules/{kernel_release}/extra/zfs "
                "-maxdepth 1 -type f "
                "\\( -name 'zfs.ko' -o -name 'zfs.ko.xz' -o -name 'zfs.ko.gz' -o -name 'zfs.ko.zst' \\) "
                "| grep -q .",
            )
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
