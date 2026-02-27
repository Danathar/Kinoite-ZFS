from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ci_tools.common import (
    normalize_owner,
    optional_env,
    require_env,
    skopeo_copy,
    skopeo_exists,
    unpack_layer_tarballs,
    write_github_outputs,
)


def _load_layer_files(akmods_dir: Path) -> list[Path]:
    # `manifest.json` lists each filesystem layer by digest.
    # Convert each digest to its local filename in the `dir:` layout.
    manifest_path = akmods_dir / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Each layer has a digest like "sha256:abcd...". In dir: layout, filename
    # is just the hash part, so we map digest -> local file path.
    layer_digests = [
        str(layer.get("digest") or "") for layer in manifest_data.get("layers", []) if layer.get("digest")
    ]
    return [akmods_dir / digest.replace("sha256:", "") for digest in layer_digests]


def _has_kernel_matching_rpm(root_dir: Path, kernel_release: str) -> bool:
    # We only trust cache reuse when an RPM exists for this exact kernel string.
    # If the cache only has RPMs for older kernels, that cache is "stale".
    rpm_dir = root_dir / "rpms" / "kmods" / "zfs"
    if not rpm_dir.exists():
        return False
    pattern = f"kmod-zfs-{kernel_release}-*.rpm"
    return any(rpm_dir.glob(pattern))


def main() -> None:
    # Workflow-provided inputs.
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    fedora_version = require_env("FEDORA_VERSION")
    kernel_release = require_env("KERNEL_RELEASE")
    # Keep backward compatibility with older workflow env name:
    # - prefer `AKMODS_REPO` (generic source repo name)
    # - fallback to `CANDIDATE_AKMODS_REPO` (older name)
    source_repo = optional_env("AKMODS_REPO") or require_env("CANDIDATE_AKMODS_REPO")

    # Source cache image reference for this Fedora major stream.
    # If source cache is missing/stale, workflow needs an akmods rebuild.
    # "Stale" means cache content was built for an older kernel release.
    source_image = f"ghcr.io/{image_org}/{source_repo}:main-{fedora_version}"
    if not skopeo_exists(f"docker://{source_image}"):
        # Source cache image is missing, so downstream build must rebuild it.
        # We write `exists=false` to GitHub step outputs so workflow `if:` rules
        # can react without parsing log text.
        write_github_outputs({"exists": "false"})
        print(f"No existing source akmods cache image for Fedora {fedora_version}; rebuild is required.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        akmods_dir = root / "akmods"
        # `skopeo copy ... dir:<path>` saves image layers so we can inspect files.
        skopeo_copy(f"docker://{source_image}", f"dir:{akmods_dir}")

        layer_files = _load_layer_files(akmods_dir)
        # Extract all filesystem layers into one temp tree for file checks.
        unpack_layer_tarballs(layer_files, root)

        if _has_kernel_matching_rpm(root, kernel_release):
            # `exists=true` means this cache can be safely reused.
            write_github_outputs({"exists": "true"})
            print(
                f"Found matching {source_image} kmod for kernel {kernel_release}; "
                "akmods rebuild can be skipped."
            )
        else:
            # `exists=false` here means the cache exists but is stale (wrong kernel).
            write_github_outputs({"exists": "false"})
            print(
                f"Cached {source_image} is present but missing kmod for kernel {kernel_release}; "
                "akmods rebuild is required."
            )


if __name__ == "__main__":
    main()
