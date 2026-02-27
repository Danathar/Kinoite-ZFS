"""
Script: ci_tools/main_configure_candidate_recipe.py
What: Rewrites recipe and ZFS containerfile values before candidate image build.
Doing: Pins `base-image`/`image-version` to this run's resolved base tag and sets `AKMODS_IMAGE` to the matching kernel tag.
Why: Keeps base image and akmods source aligned even if moving tags update during the workflow.
Goal: Build the candidate image from one consistent input set.
"""

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
    # Inputs resolved earlier in the workflow.
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    candidate_image_name = require_env("CANDIDATE_IMAGE_NAME")
    kernel_release = require_env("KERNEL_RELEASE")
    akmods_repo = require_env("AKMODS_REPO")
    base_image_name = require_env("BASE_IMAGE_NAME")
    base_image_tag = require_env("BASE_IMAGE_TAG")

    # Candidate images are pushed to a dedicated repository so the candidate step
    # cannot overwrite stable `kinoite-zfs:latest` directly.
    replace_line_starting_with(RECIPE_FILE, "name:", f"name: {candidate_image_name}")

    # Pin the base image name and immutable tag for this run.
    replace_line_starting_with(RECIPE_FILE, "base-image:", f"base-image: {base_image_name}")
    replace_line_starting_with(RECIPE_FILE, "image-version:", f"image-version: {base_image_tag}")

    # Point ZFS package install at the exact kernel-matching akmods image.
    akmods_line = (
        "AKMODS_IMAGE=\""
        f"ghcr.io/{image_org}/{akmods_repo}:main-${{FEDORA_VERSION}}-{kernel_release}"
        "\""
    )
    replace_line_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=", akmods_line)

    # Print changed lines so logs clearly show the final effective values.
    print_lines_starting_with(RECIPE_FILE, "name:")
    print_lines_starting_with(RECIPE_FILE, "base-image:")
    print_lines_starting_with(RECIPE_FILE, "image-version:")
    print_lines_starting_with(ZFS_CONTAINERFILE, "AKMODS_IMAGE=")


if __name__ == "__main__":
    main()
