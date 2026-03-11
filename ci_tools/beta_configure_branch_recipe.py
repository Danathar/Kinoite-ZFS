"""
Script: ci_tools/beta_configure_branch_recipe.py
What: Prepares a generated BlueBuild workspace for branch/PR image builds.
Doing: Copies canonical build files into a transient directory, then pins the resolved base tag and akmods source there.
Why: Keeps branch and PR runs aligned with `main` inputs without mutating checked-in files.
Goal: Build non-main images from the same base release `main` validated for that run.
"""

from __future__ import annotations

from ci_tools.common import (
    normalize_owner,
    optional_env,
    require_env,
)
from ci_tools.generated_build_context import BuildContextConfig, prepare_generated_build_context


def main() -> None:
    # Inputs prepared earlier in the branch workflow.
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    akmods_repo = require_env("AKMODS_REPO")
    akmods_tag_prefix = optional_env("AKMODS_TAG_PREFIX", "main")
    base_image_name = require_env("BASE_IMAGE_NAME")
    base_image_tag = require_env("BASE_IMAGE_TAG")

    # Point to this branch's akmods repository to avoid touching main caches.
    # "Branch-scoped" means the tag text includes the branch identifier, which
    # keeps test-only compose input separate from stable and candidate aliases.
    prepare_generated_build_context(
        BuildContextConfig(
            base_image_name=base_image_name,
            base_image_tag=base_image_tag,
            akmods_image=f"ghcr.io/{image_org}/{akmods_repo}:{akmods_tag_prefix}-${{FEDORA_VERSION}}",
        )
    )


if __name__ == "__main__":
    main()
