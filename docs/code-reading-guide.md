# Code Reading Guide

If a term is unfamiliar, check the shared glossary first:
[`docs/glossary.md`](./glossary.md)

## Purpose

This guide gives a newcomer-friendly reading order for the code in this repo,
so you can follow one full build flow from workflow trigger to published image.

## Start Here (Big Picture)

1. Read [`README.md`](../README.md) for goals, safety model, and published tags.
2. Read [`docs/architecture-overview.md`](./architecture-overview.md) for design-level flow.
3. Use this guide to read the actual workflow and Python code in order.

## Recommended Reading Order

### 1. Workflow Entry Points

Read workflow files first so you see job order and where each Python command is called.

1. Main flow: [`.github/workflows/build.yml`](../.github/workflows/build.yml)
2. Branch flow: [`.github/workflows/build-beta.yml`](../.github/workflows/build-beta.yml)
3. PR validation flow: [`.github/workflows/build-pr.yml`](../.github/workflows/build-pr.yml)

What to look for:

1. Triggers (`push`, `schedule`, `workflow_dispatch`).
2. Job order (`needs` relationships).
3. Step names and the `python3 -m ci_tools.cli <command>` calls.

### 2. CLI Dispatcher

Now read how workflow command names map to Python modules.

1. Dispatcher: [`ci_tools/cli.py`](../ci_tools/cli.py)
2. Shared helpers: [`ci_tools/common.py`](../ci_tools/common.py)
3. Shared validation-prep wrapper action: [`.github/actions/prepare-validation-build/action.yml`](../.github/actions/prepare-validation-build/action.yml)
4. Shared BlueBuild wrapper action: [`.github/actions/run-bluebuild/action.yml`](../.github/actions/run-bluebuild/action.yml)
5. Shared stable-promotion wrapper action: [`.github/actions/promote-stable/action.yml`](../.github/actions/promote-stable/action.yml)
6. Shared generated-workspace wrapper action: [`.github/actions/configure-generated-build-context/action.yml`](../.github/actions/configure-generated-build-context/action.yml)

What to look for:

1. Command map in `cli.py` (string command -> Python function).
2. Common helpers in `common.py` (`require_env`, `skopeo_*`, `write_github_output`).
3. The local composite action that wraps the repeated environment-to-Python wiring for non-main validation prep.
4. The local composite action that wraps the repeated BlueBuild `uses:` blocks for publish and validation builds.
5. The local composite action that wraps the repeated install/promote/sign steps for the main promotion job.
6. The local composite action that wraps the repeated environment-to-Python wiring for generated run-local recipe/container inputs.

### 3. Main Workflow Modules (Read In Job Order)

Read these in this sequence to match `build.yml`:

1. Resolve base inputs and kernel: [`ci_tools/main_resolve_build_inputs.py`](../ci_tools/main_resolve_build_inputs.py)
2. Write per-run manifest: [`ci_tools/main_write_build_inputs_manifest.py`](../ci_tools/main_write_build_inputs_manifest.py)
3. Check candidate/shared akmods cache: [`ci_tools/main_check_candidate_akmods_cache.py`](../ci_tools/main_check_candidate_akmods_cache.py)
4. Clone pinned akmods source: [`ci_tools/akmods_clone_pinned.py`](../ci_tools/akmods_clone_pinned.py)
5. Configure akmods target image path: [`ci_tools/akmods_configure_zfs_target.py`](../ci_tools/akmods_configure_zfs_target.py)
6. Build/publish akmods image: [`ci_tools/akmods_build_and_publish.py`](../ci_tools/akmods_build_and_publish.py)
7. Publish candidate akmods alias tags: [`ci_tools/main_publish_candidate_akmods_alias.py`](../ci_tools/main_publish_candidate_akmods_alias.py)
8. Generated-workspace wrapper action that feeds environment values into the generated-workspace Python helper: [`.github/actions/configure-generated-build-context/action.yml`](../.github/actions/configure-generated-build-context/action.yml)
9. Generate transient build inputs for candidate build: [`ci_tools/configure_generated_build_context.py`](../ci_tools/configure_generated_build_context.py)
10. Promotion wrapper action that installs required tools and dispatches the promotion helpers: [`.github/actions/promote-stable/action.yml`](../.github/actions/promote-stable/action.yml)
11. Promote candidate to stable tags: [`ci_tools/main_promote_stable.py`](../ci_tools/main_promote_stable.py)
12. Re-sign promoted stable digest in the stable repository path: [`ci_tools/main_sign_promoted_stable.py`](../ci_tools/main_sign_promoted_stable.py)

### 4. Branch Workflow Modules (Read In Job Order)

Read these in this sequence to match `build-beta.yml`:

1. Compute branch-safe tag parts: [`ci_tools/beta_compute_branch_metadata.py`](../ci_tools/beta_compute_branch_metadata.py)
2. Shared validation-prep wrapper action that feeds workflow env into the Python helper: [`.github/actions/prepare-validation-build/action.yml`](../.github/actions/prepare-validation-build/action.yml)
3. Shared read-only validation prep (input resolution + shared-cache verification): [`ci_tools/prepare_validation_build.py`](../ci_tools/prepare_validation_build.py)
4. Underlying input resolver reused by that shared prep command: [`ci_tools/main_resolve_build_inputs.py`](../ci_tools/main_resolve_build_inputs.py)
5. Underlying akmods cache checker reused by that shared prep command: [`ci_tools/main_check_candidate_akmods_cache.py`](../ci_tools/main_check_candidate_akmods_cache.py)
6. Publish branch alias tag in candidate repo: [`ci_tools/beta_publish_branch_akmods_alias.py`](../ci_tools/beta_publish_branch_akmods_alias.py)
7. Generate branch/PR build inputs: [`ci_tools/configure_generated_build_context.py`](../ci_tools/configure_generated_build_context.py)

### 5. Build Inputs Used By Python Modules

Read these next so you can connect Python edits to actual build files:

1. Canonical recipe source copied into generated workspace: [`recipes/recipe.yml`](../recipes/recipe.yml)
2. Canonical akmods containerfile source copied into generated workspace: [`containerfiles/zfs-akmods/Containerfile`](../containerfiles/zfs-akmods/Containerfile)
3. Generated workspace builder: [`ci_tools/generated_build_context.py`](../ci_tools/generated_build_context.py)
4. Optional lock replay file: [`ci/inputs.lock.json`](../ci/inputs.lock.json)

Important terms:

1. `working directory`: the folder a build tool treats as its local root for file lookups.
2. `generated workspace`: a transient directory created during CI so the build can use run-specific files without editing tracked source files.
3. `build context`: the set of local files made visible to the build tool for one run.

### 6. Tests (How Logic Is Verified)

Read tests last to confirm expected behavior:

1. Command dispatch checks: [`tests/test_cli.py`](../tests/test_cli.py)
2. Input resolution behavior: [`tests/test_main_resolve_build_inputs.py`](../tests/test_main_resolve_build_inputs.py)
3. Candidate alias behavior: [`tests/test_main_publish_candidate_akmods_alias.py`](../tests/test_main_publish_candidate_akmods_alias.py)
4. Akmods build env behavior: [`tests/test_akmods_build_and_publish.py`](../tests/test_akmods_build_and_publish.py)
5. Branch metadata behavior: [`tests/test_beta_compute_branch_metadata.py`](../tests/test_beta_compute_branch_metadata.py)
6. Shared generated-build-context behavior: [`tests/test_configure_generated_build_context.py`](../tests/test_configure_generated_build_context.py)
7. Shared non-main validation prep behavior: [`tests/test_prepare_validation_build.py`](../tests/test_prepare_validation_build.py)
8. Promotion signing behavior: [`tests/test_main_sign_promoted_stable.py`](../tests/test_main_sign_promoted_stable.py)

## Trace One Value End-To-End (`kernel_release`)

If you want to practice reading code flow, trace `kernel_release`:

1. Resolved in [`ci_tools/main_resolve_build_inputs.py`](../ci_tools/main_resolve_build_inputs.py).
2. Written to step outputs (`GITHUB_OUTPUT`) together with `kernel_releases` and consumed by later jobs.
3. Used as the newest/base-primary kernel identifier in logs and debug tags.
4. The full `kernel_releases` list is used for akmods cache checks and rebuild decisions.
5. Used when rewriting recipe/container inputs before candidate compose.

This single value is a good way to see how data moves across jobs and files.

## Practical Tip

When reading any module:

1. Start at `main()` to see required environment variables.
2. Follow helper calls in order.
3. Match print/error messages to workflow logs so you can debug runs quickly.
