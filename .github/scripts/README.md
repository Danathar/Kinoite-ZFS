# Workflow Command Map

Workflows in this repo call Python through one shared CLI entrypoint:

- `python3 -m ci_tools.cli <command>`

That CLI dispatches to the real implementation in [`ci_tools/`](../../ci_tools).
This keeps workflow YAML focused on job order, permissions, and data flow.

If a term is unfamiliar, check the shared glossary first:
[`docs/glossary.md`](../../docs/glossary.md)

## Quick Terms

- `composite action`: a local reusable GitHub Action that bundles several workflow steps behind one `uses:` line.
- `image ref`: text that points to a container image, like `name:tag` (moving label) or `name@sha256:digest` (exact snapshot).
- `tag`: a human-readable image label like `latest` or `main-43`.
- `branch-scoped`: a tag/name that includes the branch identifier so test artifacts stay isolated.
- `skopeo`: command-line tool that reads/copies container images without starting a container.
- `GITHUB_OUTPUT`: file path GitHub Actions gives each step; writing `name=value` lines there exposes outputs to later steps.

## Local Action Map

| Local action | Purpose |
|---|---|
| [`.github/actions/prepare-main-build-inputs/action.yml`](../actions/prepare-main-build-inputs/action.yml) | Wrap the repeated environment-to-Python wiring that resolves pinned main-workflow inputs, uploads the build-input manifest artifact, and records whether shared akmods cache reuse is safe. |
| [`.github/actions/prepare-validation-build/action.yml`](../actions/prepare-validation-build/action.yml) | Wrap the repeated environment-to-Python wiring that resolves pinned non-main inputs and verifies the shared akmods source before compose. |
| [`.github/actions/configure-generated-build-context/action.yml`](../actions/configure-generated-build-context/action.yml) | Wrap the repeated environment-to-Python wiring that generates the transient BlueBuild workspace for one run. |
| [`.github/actions/run-bluebuild/action.yml`](../actions/run-bluebuild/action.yml) | Wrap the repeated BlueBuild compose step for publish and validation modes. |
| [`.github/actions/promote-stable/action.yml`](../actions/promote-stable/action.yml) | Wrap the repeated install/promote/sign steps in the main stable-promotion job. |

## CLI Command Map

| Workflow step (example) | CLI command | Python module |
|---|---|---|
| Resolve build inputs (latest mode or lock replay mode) | `main-resolve-build-inputs` | `ci_tools.main_resolve_build_inputs` |
| Write build inputs manifest | `main-write-build-inputs-manifest` | `ci_tools.main_write_build_inputs_manifest` |
| Check for existing shared self-hosted zfs akmods image | `main-check-candidate-akmods-cache` | `ci_tools.main_check_candidate_akmods_cache` |
| Resolve PR/branch validation inputs and verify shared akmods source | `prepare-validation-build` | `ci_tools.prepare_validation_build` |
| Generate run-local recipe/container inputs in `.generated/bluebuild/` | `configure-generated-build-context` | `ci_tools.configure_generated_build_context` |
| Publish candidate akmods alias tags from shared source | `main-publish-candidate-akmods-alias` | `ci_tools.main_publish_candidate_akmods_alias` |
| Smoke-test the published candidate image before promotion | `main-smoke-test-candidate-image` | `ci_tools.main_smoke_test_candidate_image` |
| Promote candidate image and akmods cache to stable tags | `main-promote-stable` | `ci_tools.main_promote_stable` |
| Sign promoted stable image digest | `main-sign-promoted-stable` | `ci_tools.main_sign_promoted_stable` |
| Compute branch-safe public alias tag prefix | `beta-compute-branch-metadata` | `ci_tools.beta_compute_branch_metadata` |
| Publish branch akmods alias tag in candidate repo | `beta-publish-branch-akmods-alias` | `ci_tools.beta_publish_branch_akmods_alias` |
| Clone pinned upstream akmods tooling | `akmods-clone-pinned` | `ci_tools.akmods_clone_pinned` |
| Configure target image path for the akmods build wrapper | `akmods-configure-zfs-target` | `ci_tools.akmods_configure_zfs_target` |
| Build and publish self-hosted zfs akmods image | `akmods-build-and-publish` | `ci_tools.akmods_build_and_publish` |

## Build Input Note

- Canonical recipe source lives at [`recipes/recipe.yml`](../../recipes/recipe.yml).
- Canonical akmods Containerfile source lives at [`containerfiles/zfs-akmods/Containerfile`](../../containerfiles/zfs-akmods/Containerfile).
- Workflows do not edit those tracked source files in place anymore.
- Instead, [`ci_tools/generated_build_context.py`](../../ci_tools/generated_build_context.py) copies them into `.generated/bluebuild/` and applies run-specific values there.

This matters because generated inputs are easier to reason about than mutating checked-in files during CI.
