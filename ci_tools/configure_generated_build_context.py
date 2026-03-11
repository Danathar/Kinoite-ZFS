"""
Script: ci_tools/configure_generated_build_context.py
What: Prepares the generated BlueBuild workspace from workflow environment values.
Doing: Reads base-image and akmods settings from CI env, then calls the shared workspace generator.
Why: Main, branch, and PR builds all shape the same generated workspace with only small value differences.
Goal: Keep one command entrypoint for build-context generation instead of separate per-workflow wrappers.
"""

from __future__ import annotations

from ci_tools.common import normalize_owner, optional_env, require_env
from ci_tools.generated_build_context import BuildContextConfig, prepare_generated_build_context


def main() -> None:
    # Inputs resolved earlier in the workflow.
    # Normalize owner means: convert to lowercase so generated registry paths
    # stay consistent even if the GitHub owner text includes uppercase letters.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    akmods_repo = require_env("AKMODS_REPO")
    base_image_name = require_env("BASE_IMAGE_NAME")
    base_image_tag = require_env("BASE_IMAGE_TAG")

    # Optional inputs let one command cover candidate, branch, and PR flows:
    # - `IMAGE_NAME` is set only when a workflow needs a different publish repo
    #   name (for example the candidate image repository).
    # - `AKMODS_TAG_PREFIX` defaults to `main`, which is the shared Fedora-wide
    #   akmods tag prefix used by candidate and PR validation. Branch runs set a
    #   branch-scoped prefix so their compose input stays isolated.
    image_name = optional_env("IMAGE_NAME").strip() or None
    # Treat an empty string the same as "unset" so workflow wrappers can safely
    # forward optional inputs without accidentally erasing the shared `main`
    # prefix used by candidate and PR builds.
    akmods_tag_prefix = optional_env("AKMODS_TAG_PREFIX").strip() or "main"

    prepare_generated_build_context(
        BuildContextConfig(
            image_name=image_name,
            base_image_name=base_image_name,
            base_image_tag=base_image_tag,
            akmods_image=f"ghcr.io/{image_org}/{akmods_repo}:{akmods_tag_prefix}-${{FEDORA_VERSION}}",
        )
    )


if __name__ == "__main__":
    main()
