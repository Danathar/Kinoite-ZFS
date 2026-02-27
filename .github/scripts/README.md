# Workflow Command Map

Workflows now call Python directly with one shared entrypoint:

- `python3 -m ci_tools.cli <command>`

The CLI dispatches to the real module in [`ci_tools/`](../../ci_tools).
This keeps workflow logic readable and avoids extra wrapper layers.

## Quick Terms

- `normalize`: make text consistent. In this repo, normalize owner/org means lowercase it so image paths are stable.
- `image ref`: text that points to a container image, like `name:tag` (can move) or `name@sha256:digest` (exact snapshot).
- `tag`: a label on an image, like `latest` or `main-43`.
- `skopeo`: command-line tool that reads/copies container images without starting a container.
- `GITHUB_OUTPUT`: a file path GitHub Actions gives each step; writing `name=value` lines there creates outputs for later steps.

## Step Mapping Table

| Workflow step (example) | CLI command | Python module |
|---|---|---|
| Resolve build inputs (latest mode or lock replay mode) | `main-resolve-build-inputs` | `ci_tools.main_resolve_build_inputs` |
| Write build inputs manifest | `main-write-build-inputs-manifest` | `ci_tools.main_write_build_inputs_manifest` |
| Check for existing self-hosted zfs akmods source image tag | `main-check-candidate-akmods-cache` | `ci_tools.main_check_candidate_akmods_cache` |
| Publish candidate akmods alias tags from shared source | `main-publish-candidate-akmods-alias` | `ci_tools.main_publish_candidate_akmods_alias` |
| Set kernel-matched akmods source and pin base tag in recipe | `main-configure-candidate-recipe` | `ci_tools.main_configure_candidate_recipe` |
| Promote candidate image and akmods cache to stable tags | `main-promote-stable` | `ci_tools.main_promote_stable` |
| Compute branch-safe public alias tag prefix | `beta-compute-branch-metadata` | `ci_tools.beta_compute_branch_metadata` |
| Detect Fedora major version for Kinoite latest | `beta-detect-fedora-version` | `ci_tools.beta_detect_fedora_version` |
| Check for existing shared self-hosted zfs akmods image tag | `beta-check-branch-akmods-cache` | `ci_tools.beta_check_branch_akmods_cache` |
| Publish branch akmods alias tag in candidate repo | `beta-publish-branch-akmods-alias` | `ci_tools.beta_publish_branch_akmods_alias` |
| Set branch akmods source in recipe | `beta-configure-branch-recipe` | `ci_tools.beta_configure_branch_recipe` |
| Clone upstream akmods tooling | `akmods-clone-pinned` | `ci_tools.akmods_clone_pinned` |
| Configure zfs target in branch/candidate namespace | `akmods-configure-zfs-target` | `ci_tools.akmods_configure_zfs_target` |
| Build and publish self-hosted zfs akmods image | `akmods-build-and-publish` | `ci_tools.akmods_build_and_publish` |

## Containerfile Note

- `AKMODS_IMAGE` is defined in [`containerfiles/zfs-akmods/Containerfile`](../../containerfiles/zfs-akmods/Containerfile).
- Main and branch configure steps rewrite that line in the Containerfile.
- Main also rewrites `base-image` and `image-version` in [`recipes/recipe.yml`](../../recipes/recipe.yml) to a fixed tag for the current run.
