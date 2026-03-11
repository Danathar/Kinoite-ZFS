"""
Script: ci_tools/main_configure_candidate_recipe.py
What: Prepares a generated BlueBuild workspace before candidate image build.
Doing: Copies canonical build files into a transient directory, then pins base + candidate akmods values there.
Why: Prevents input drift during longer runs without mutating checked-in source files.
Goal: Build the candidate image from one consistent generated input set.
"""

from __future__ import annotations

from ci_tools.common import (
    normalize_owner,
    require_env,
)
from ci_tools.generated_build_context import BuildContextConfig, prepare_generated_build_context


def main() -> None:
    # Inputs resolved earlier in the workflow.
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    candidate_image_name = require_env("CANDIDATE_IMAGE_NAME")
    akmods_repo = require_env("AKMODS_REPO")
    base_image_name = require_env("BASE_IMAGE_NAME")
    base_image_tag = require_env("BASE_IMAGE_TAG")

    # Point ZFS package install at the candidate-repo Fedora-wide cache tag.
    # "Fedora-wide" here means one cache image that can carry RPMs for more
    # than one installed kernel in the same base image. The workflow copies
    # this tag into the candidate repo earlier in the same run, so compose does
    # not depend on whatever happens to be in the stable repo later.
    prepare_generated_build_context(
        BuildContextConfig(
            # Candidate images are pushed to a dedicated repository so this step
            # cannot overwrite stable `kinoite-zfs:latest` directly.
            image_name=candidate_image_name,
            base_image_name=base_image_name,
            base_image_tag=base_image_tag,
            akmods_image=f"ghcr.io/{image_org}/{akmods_repo}:main-${{FEDORA_VERSION}}",
        )
    )


if __name__ == "__main__":
    main()
