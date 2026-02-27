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
    akmods_repo = require_env("AKMODS_REPO")
    akmods_tag_prefix = require_env("AKMODS_TAG_PREFIX")

    # Keep branch builds on a real upstream base tag.
    # Important: recipe `image-version` selects the base-image tag to pull
    # (`base-image:image-version`), so this must be a tag that exists in
    # `ghcr.io/ublue-os/kinoite-main` (for example `latest`).
    # Branch-specific publish tags are handled by BlueBuild's branch tagging,
    # not by setting `image-version` to the branch name.
    replace_line_starting_with(RECIPE_FILE, "image-version:", "image-version: latest")
    # Point to this branch's akmods tag to avoid touching main caches.
    # We keep one shared candidate repo and isolate by branch-specific tags
    # (example: `br-my-branch-43`), which avoids private per-branch repos.
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
