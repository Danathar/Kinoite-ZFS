"""
Script: ci_tools/beta_configure_branch_recipe.py
What: Rewrites recipe and containerfile values for branch image builds.
Doing: Sets the branch image tag and the branch akmods source tag.
Why: Keeps branch test runs separate from stable tags.
Goal: Build branch images from branch-scoped references.
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

    # Keep branch builds on a real upstream base tag.
    # Important: recipe `image-version` selects the base-image tag to pull
    # (`base-image:image-version`), so this must be a tag that exists in
    # `ghcr.io/ublue-os/kinoite-main` (for example `latest`).
    # Branch-specific publish tags are handled by BlueBuild's branch tagging,
    # not by setting `image-version` to the branch name.
    replace_line_starting_with(RECIPE_FILE, "image-version:", "image-version: latest")
    # Point to this branch's akmods repository to avoid touching main caches.
    # This line is inserted into the Containerfile and expanded later at build time.
    akmods_line = (
        "AKMODS_IMAGE=\""
        f"ghcr.io/{image_org}/{akmods_repo}:{akmods_tag_prefix}-${{FEDORA_VERSION}}"
        "\""
    )
    replace_line_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=", akmods_line)

    print_lines_starting_with(RECIPE_FILE, "image-version:")
    print_lines_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=")


if __name__ == "__main__":
    main()
