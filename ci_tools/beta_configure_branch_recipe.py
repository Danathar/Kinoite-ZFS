"""
Script: ci_tools/beta_configure_branch_recipe.py
What: Rewrites recipe and containerfile values for branch image builds.
Doing: Pins the resolved upstream base tag and sets the branch akmods source tag.
Why: Keeps branch test runs separate from stable tags without drifting from `main` inputs.
Goal: Build branch images from the same base release `main` validated for that run.
"""

from __future__ import annotations

from pathlib import Path

from ci_tools.common import (
    normalize_owner,
    optional_env,
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
    akmods_repo = require_env("AKMODS_REPO")
    akmods_tag_prefix = optional_env("AKMODS_TAG_PREFIX", "main")
    base_image_name = require_env("BASE_IMAGE_NAME")
    base_image_tag = require_env("BASE_IMAGE_TAG")

    # Pin the base image name and immutable-looking tag resolved earlier in CI.
    # This keeps branch and PR validation on the same upstream base release that
    # `main` inspected, instead of letting `latest` move underneath longer runs.
    replace_line_starting_with(RECIPE_FILE, "base-image:", f"base-image: {base_image_name}")
    replace_line_starting_with(RECIPE_FILE, "image-version:", f"image-version: {base_image_tag}")

    # Point to this branch's akmods repository to avoid touching main caches.
    # This line is inserted into the Containerfile and expanded later at build time.
    akmods_line = (
        "AKMODS_IMAGE=\""
        f"ghcr.io/{image_org}/{akmods_repo}:{akmods_tag_prefix}-${{FEDORA_VERSION}}"
        "\""
    )
    replace_line_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=", akmods_line)

    print_lines_starting_with(RECIPE_FILE, "base-image:")
    print_lines_starting_with(RECIPE_FILE, "image-version:")
    print_lines_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=")


if __name__ == "__main__":
    main()
