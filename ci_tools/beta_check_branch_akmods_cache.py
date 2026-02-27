"""
Script: ci_tools/beta_check_branch_akmods_cache.py
What: Checks whether existing akmods cache has an RPM for the current kernel.
Doing: Pulls the cache image, unpacks layers, searches for `kmod-zfs-<kernel>-*.rpm`, then writes `exists=true|false`.
Why: Reuse cache when safe, but rebuild when cache is old for this kernel.
Goal: Decide whether branch workflow must rebuild akmods.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ci_tools.common import (
    normalize_owner,
    require_env,
    skopeo_copy,
    skopeo_exists,
    unpack_layer_tarballs,
    write_github_outputs,
)


def _load_layer_files(akmods_dir: Path) -> list[Path]:
    # `manifest.json` tells us which layer files contain the cached RPM content.
    manifest_path = akmods_dir / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    layer_digests = [
        str(layer.get("digest") or "") for layer in manifest_data.get("layers", []) if layer.get("digest")
    ]
    return [akmods_dir / digest.replace("sha256:", "") for digest in layer_digests]


def _has_kernel_matching_rpm(root_dir: Path, kernel_release: str) -> bool:
    # Cache is only safe if it includes a kmod RPM built for the exact kernel.
    rpm_dir = root_dir / "rpms" / "kmods" / "zfs"
    if not rpm_dir.exists():
        return False
    pattern = f"kmod-zfs-{kernel_release}-*.rpm"
    return any(rpm_dir.glob(pattern))


def main() -> None:
    # Inputs passed from the workflow step.
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    fedora_version = require_env("FEDORA_VERSION")
    kernel_release = require_env("KERNEL_RELEASE")
    akmods_repo = require_env("AKMODS_REPO")

    # Branch-specific cache image for this Fedora major version.
    akmods_image = f"ghcr.io/{image_org}/{akmods_repo}:main-{fedora_version}"
    if not skopeo_exists(f"docker://{akmods_image}"):
        write_github_outputs({"exists": "false"})
        print(f"No existing {akmods_image}; akmods rebuild is required.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        akmods_dir = root / "akmods"
        # Pull image layers into a local directory so we can inspect files directly.
        skopeo_copy(f"docker://{akmods_image}", f"dir:{akmods_dir}")

        layer_files = _load_layer_files(akmods_dir)
        # Merge layer contents in temp dir so we can search for exact RPM files.
        unpack_layer_tarballs(layer_files, root)

        if _has_kernel_matching_rpm(root, kernel_release):
            write_github_outputs({"exists": "true"})
            print(
                f"Found matching {akmods_image} kmod for kernel {kernel_release}; "
                "akmods rebuild can be skipped."
            )
        else:
            write_github_outputs({"exists": "false"})
            print(
                f"Cached {akmods_image} is present but missing kmod for kernel {kernel_release}; "
                "akmods rebuild is required."
            )


if __name__ == "__main__":
    main()
