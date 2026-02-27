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
    # `manifest.json` lists each filesystem layer by digest.
    # Convert each digest to its local filename in the `dir:` layout.
    manifest_path = akmods_dir / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    layer_digests = [
        str(layer.get("digest") or "") for layer in manifest_data.get("layers", []) if layer.get("digest")
    ]
    return [akmods_dir / digest.replace("sha256:", "") for digest in layer_digests]


def _has_kernel_matching_rpm(root_dir: Path, kernel_release: str) -> bool:
    # We only trust cache reuse when an RPM exists for this exact kernel string.
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
    candidate_repo = require_env("CANDIDATE_AKMODS_REPO")
    stable_repo = require_env("STABLE_AKMODS_REPO")

    candidate_image = f"ghcr.io/{image_org}/{candidate_repo}:main-{fedora_version}"
    stable_image = f"ghcr.io/{image_org}/{stable_repo}:main-{fedora_version}"

    # Prefer candidate cache, then optionally fall back to stable cache.
    selected_image = ""
    if skopeo_exists(f"docker://{candidate_image}"):
        selected_image = candidate_image
        print(f"Using candidate cache source {selected_image}")
    elif candidate_repo != stable_repo and skopeo_exists(f"docker://{stable_image}"):
        selected_image = stable_image
        print(f"Candidate cache tag missing; falling back to stable cache source {selected_image}")

    if not selected_image:
        write_github_outputs({"exists": "false"})
        print(
            "No existing candidate/stable akmods cache image for "
            f"Fedora {fedora_version}; akmods rebuild is required."
        )
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        akmods_dir = root / "akmods"
        # `skopeo copy ... dir:<path>` saves image layers so we can inspect files.
        skopeo_copy(f"docker://{selected_image}", f"dir:{akmods_dir}")

        layer_files = _load_layer_files(akmods_dir)
        unpack_layer_tarballs(layer_files, root)

        if _has_kernel_matching_rpm(root, kernel_release):
            write_github_outputs({"exists": "true"})
            print(
                f"Found matching {selected_image} kmod for kernel {kernel_release}; "
                "akmods rebuild can be skipped."
            )
        else:
            write_github_outputs({"exists": "false"})
            print(
                f"Cached {selected_image} is present but missing kmod for kernel {kernel_release}; "
                "akmods rebuild is required."
            )


if __name__ == "__main__":
    main()
