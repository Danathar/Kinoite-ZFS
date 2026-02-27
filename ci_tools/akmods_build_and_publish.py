"""
Script: ci_tools/akmods_build_and_publish.py
What: Runs the akmods build and publish lifecycle from `/tmp/akmods`.
Doing: Optionally pins kernel metadata, then runs `just build`, `just login`, `just push`, and `just manifest`.
Why: Keeps publish behavior in one place instead of duplicating shell commands in workflows.
Goal: Produce and publish the ZFS akmods cache image and manifest for the current run.
"""

from __future__ import annotations

import json
from pathlib import Path

from ci_tools.common import CiToolError, optional_env, require_env, run_cmd


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


def write_kernel_cache_file() -> None:
    # If no explicit kernel release is given, keep default upstream behavior.
    kernel_release = optional_env("KERNEL_RELEASE").strip()
    if not kernel_release:
        return

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


def main() -> None:
    # All akmods commands run from /tmp/akmods after the clone step.
    if not AKMODS_WORKTREE.exists():
        raise CiToolError(f"Expected akmods checkout at {AKMODS_WORKTREE}")

    write_kernel_cache_file()

    # Run upstream akmods lifecycle in order.
    run_cmd(["just", "build"], cwd=str(AKMODS_WORKTREE), capture_output=False)
    run_cmd(["just", "login"], cwd=str(AKMODS_WORKTREE), capture_output=False)
    run_cmd(["just", "push"], cwd=str(AKMODS_WORKTREE), capture_output=False)
    run_cmd(["just", "manifest"], cwd=str(AKMODS_WORKTREE), capture_output=False)


if __name__ == "__main__":
    main()
