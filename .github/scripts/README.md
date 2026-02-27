# Workflow Script Layout

These files are workflow entry points.

Each `.sh` file is now a thin wrapper that calls a Python module in [`ci_tools/`](../../ci_tools).
This keeps workflow logic readable, testable, and easier to maintain.

## Quick Terms

- `normalize`: make text consistent. In this repo, when we normalize owner/org names, we convert them to lowercase for registry paths.
- `image ref`: text that points to a container image, like `name:tag` (moving) or `name@sha256:digest` (exact).
- `skopeo`: a command-line tool that inspects or copies container images without running them.
- `GITHUB_OUTPUT`: a file path provided by GitHub Actions; writing `name=value` lines there creates step outputs for later steps.

## Main Pipeline Entry Points

- [`.github/scripts/main/resolve-build-inputs.sh`](./main/resolve-build-inputs.sh) -> `python3 -m ci_tools.main_resolve_build_inputs`
- [`.github/scripts/main/write-build-inputs-manifest.sh`](./main/write-build-inputs-manifest.sh) -> `python3 -m ci_tools.main_write_build_inputs_manifest`
- [`.github/scripts/main/check-candidate-akmods-cache.sh`](./main/check-candidate-akmods-cache.sh) -> `python3 -m ci_tools.main_check_candidate_akmods_cache`
- [`.github/scripts/main/configure-candidate-recipe.sh`](./main/configure-candidate-recipe.sh) -> `python3 -m ci_tools.main_configure_candidate_recipe`
- [`.github/scripts/main/promote-stable.sh`](./main/promote-stable.sh) -> `python3 -m ci_tools.main_promote_stable`

## Branch Pipeline Entry Points

- [`.github/scripts/beta/compute-branch-metadata.sh`](./beta/compute-branch-metadata.sh) -> `python3 -m ci_tools.beta_compute_branch_metadata`
- [`.github/scripts/beta/detect-fedora-version.sh`](./beta/detect-fedora-version.sh) -> `python3 -m ci_tools.beta_detect_fedora_version`
- [`.github/scripts/beta/check-branch-akmods-cache.sh`](./beta/check-branch-akmods-cache.sh) -> `python3 -m ci_tools.beta_check_branch_akmods_cache`
- [`.github/scripts/beta/configure-branch-recipe.sh`](./beta/configure-branch-recipe.sh) -> `python3 -m ci_tools.beta_configure_branch_recipe`

## Shared Akmods Entry Points

These also use thin shell wrappers that call Python modules:

- [`akmods/clone-pinned-akmods.sh`](./akmods/clone-pinned-akmods.sh) -> `python3 -m ci_tools.akmods_clone_pinned`
- [`akmods/configure-zfs-target.sh`](./akmods/configure-zfs-target.sh) -> `python3 -m ci_tools.akmods_configure_zfs_target`
- [`akmods/build-and-publish.sh`](./akmods/build-and-publish.sh) -> `python3 -m ci_tools.akmods_build_and_publish`

## Containerfile Note

- `AKMODS_IMAGE` is defined in [`containerfiles/zfs-akmods/Containerfile`](../../containerfiles/zfs-akmods/Containerfile).
- Main and branch configure steps rewrite that line in the Containerfile.
- Main also rewrites `base-image` and `image-version` in [`recipes/recipe.yml`](../../recipes/recipe.yml) to a fixed tag for the current run.
