from __future__ import annotations

from pathlib import Path

from ci_tools.common import (
    normalize_owner,
    print_lines_starting_with,
    replace_line_starting_with,
    require_env,
)


RECIPE_FILE = Path("recipes/recipe.yml")
ZFS_CONTAINERFILE = Path("containerfiles/zfs-akmods/Containerfile")


def main() -> None:
    # Inputs prepared earlier in the branch workflow.
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    image_tag = require_env("IMAGE_TAG")
    akmods_repo = require_env("AKMODS_REPO")

    # Branch builds use a branch-specific image tag.
    replace_line_starting_with(RECIPE_FILE, "image-version:", f"image-version: {image_tag}")
    # Point to this branch's akmods repository to avoid touching main caches.
    akmods_line = (
        "AKMODS_IMAGE=\""
        f"ghcr.io/{image_org}/{akmods_repo}:main-${{FEDORA_VERSION}}"
        "\""
    )
    replace_line_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=", akmods_line)

    print_lines_starting_with(RECIPE_FILE, "image-version:")
    print_lines_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=")


if __name__ == "__main__":
    main()
