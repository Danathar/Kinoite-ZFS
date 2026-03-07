"""
Script: ci_tools/akmods_build_and_publish.py
What: Builds and publishes the ZFS akmods image from `/tmp/akmods`.
Doing: Optionally pins kernel info, then runs `just build`, `just login`, `just push`, and `just manifest`.
Why: Keeps these steps in one file instead of repeated workflow shell blocks.
Goal: Publish the akmods image and manifest used by later build steps.
"""

from __future__ import annotations

import json
from pathlib import Path

from ci_tools.common import CiToolError, kernel_releases_from_env, optional_env, require_env, run_cmd


AKMODS_WORKTREE = Path("/tmp/akmods")


def kernel_name_for_flavor(kernel_flavor: str) -> str:
    """
    Map a kernel flavor name to the package base name expected by akmods tooling.

    Current rule in upstream scripts:
    - flavors starting with `longterm` use `kernel-longterm`
    - all others use `kernel`
    """
    if kernel_flavor.startswith("longterm"):
        return "kernel-longterm"
    return "kernel"


def kernel_major_minor_patch(kernel_release: str) -> str:
    """Keep only the first three dot-separated parts of the kernel release."""
    return ".".join(kernel_release.split(".")[:3])


def build_kernel_cache_document(
    *,
    kernel_release: str,
    kernel_flavor: str,
    akmods_version: str,
    build_root: Path,
    kcpath_override: str,
) -> tuple[dict[str, str], Path]:
    """
    Build the cache JSON payload and destination path used by akmods tooling.

    Return value is a tuple:
    1. `payload` (dict): JSON fields that upstream scripts read.
    2. `cache_json_path` (Path): where that JSON should be written.
    """
    # Upstream cache layout groups data by "<kernel_flavor>-<fedora_version>".
    build_id = f"{kernel_flavor}-{akmods_version}"
    # KCWD/KCPATH names are expected by upstream akmods scripts.
    kcwd = build_root / build_id / "KCWD"
    kcpath = Path(kcpath_override) if kcpath_override else (kcwd / "rpms")
    cache_json_path = kcpath / "cache.json"

    # This object becomes cache.json.
    # Keeping it as a dict makes the structure explicit and easy to test.
    payload = {
        "kernel_build_tag": "",
        "kernel_flavor": kernel_flavor,
        "kernel_major_minor_patch": kernel_major_minor_patch(kernel_release),
        "kernel_release": kernel_release,
        "kernel_name": kernel_name_for_flavor(kernel_flavor),
        "KCWD": str(kcwd),
        "KCPATH": str(kcpath),
    }
    return payload, cache_json_path


def write_kernel_cache_file(*, kernel_release: str) -> None:
    # When kernel pinning is enabled, these values must also be set.
    kernel_flavor = require_env("AKMODS_KERNEL")
    akmods_version = require_env("AKMODS_VERSION")

    # Allow override paths from env, but keep a stable default layout.
    build_root_default = str(AKMODS_WORKTREE / "build")
    build_root = Path(optional_env("AKMODS_BUILDDIR", build_root_default))
    kcpath_override = optional_env("KCPATH")

    # Build both the JSON object and output file path from one helper function.
    payload, cache_json_path = build_kernel_cache_document(
        kernel_release=kernel_release,
        kernel_flavor=kernel_flavor,
        akmods_version=akmods_version,
        build_root=build_root,
        kcpath_override=kcpath_override,
    )

    cache_json_path.parent.mkdir(parents=True, exist_ok=True)
    cache_json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Pinned akmods kernel release to {kernel_release}")
    print(f"Seeded {cache_json_path}")


def build_and_publish_kernel_release(kernel_release: str) -> None:
    """
    Build and publish one kernel-specific akmods payload.

    We intentionally reuse the same Fedora-wide cache path (`main-<fedora>`) for
    each kernel in the run. That lets the shared `main-<fedora>` image collect
    RPMs for more than one installed kernel when the upstream base image keeps a
    fallback kernel under `/lib/modules`.
    """
    print(f"Building akmods for kernel release: {kernel_release}")
    write_kernel_cache_file(kernel_release=kernel_release)

    # Upstream tooling reads the cache metadata we just wrote and publishes both
    # the Fedora-wide cache tag and the kernel-specific tag for this release.
    run_cmd(["just", "build"], cwd=str(AKMODS_WORKTREE), capture_output=False)
    run_cmd(["just", "push"], cwd=str(AKMODS_WORKTREE), capture_output=False)
    run_cmd(["just", "manifest"], cwd=str(AKMODS_WORKTREE), capture_output=False)


def main() -> None:
    # All akmods commands run from /tmp/akmods after the clone step.
    if not AKMODS_WORKTREE.exists():
        raise CiToolError(f"Expected akmods checkout at {AKMODS_WORKTREE}")

    kernel_releases = kernel_releases_from_env()
    if not kernel_releases:
        # If no explicit kernel list is provided, keep default upstream behavior.
        run_cmd(["just", "build"], cwd=str(AKMODS_WORKTREE), capture_output=False)
        run_cmd(["just", "login"], cwd=str(AKMODS_WORKTREE), capture_output=False)
        run_cmd(["just", "push"], cwd=str(AKMODS_WORKTREE), capture_output=False)
        run_cmd(["just", "manifest"], cwd=str(AKMODS_WORKTREE), capture_output=False)
        return

    # Authenticate once, then publish one kernel-specific payload at a time.
    # This keeps the loop readable in logs and avoids repeated login churn.
    run_cmd(["just", "login"], cwd=str(AKMODS_WORKTREE), capture_output=False)
    for kernel_release in kernel_releases:
        build_and_publish_kernel_release(kernel_release)


if __name__ == "__main__":
    main()
