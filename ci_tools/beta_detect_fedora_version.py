from __future__ import annotations

from ci_tools.common import (
    CiToolError,
    extract_fedora_version,
    skopeo_inspect_json,
    write_github_outputs,
)


def main() -> None:
    # Read the current upstream Kinoite stream metadata from GHCR.
    # "Stream" means the moving sequence of published image/kernel versions.
    inspect_json = skopeo_inspect_json("docker://ghcr.io/ublue-os/kinoite-main:latest")
    # `Labels` is a metadata object (dictionary) on the image manifest.
    labels = inspect_json.get("Labels") or {}
    kernel_release = str(labels.get("ostree.linux") or "")
    if not kernel_release:
        raise CiToolError(
            "Failed to read ostree.linux label from ghcr.io/ublue-os/kinoite-main:latest"
        )

    fedora_version = extract_fedora_version(kernel_release)
    write_github_outputs({"version": fedora_version, "kernel_release": kernel_release})

    print(f"Detected Fedora version: {fedora_version}")
    print(f"Detected kernel release: {kernel_release}")


if __name__ == "__main__":
    main()
