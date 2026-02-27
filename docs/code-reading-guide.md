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

What to look for:

1. Command map in `cli.py` (string command -> Python function).
2. Common helpers in `common.py` (`require_env`, `skopeo_*`, `write_github_output`).

### 3. Main Workflow Modules (Read In Job Order)

Read these in this sequence to match `build.yml`:

1. Resolve base inputs and kernel: [`ci_tools/main_resolve_build_inputs.py`](../ci_tools/main_resolve_build_inputs.py)
2. Write per-run manifest: [`ci_tools/main_write_build_inputs_manifest.py`](../ci_tools/main_write_build_inputs_manifest.py)
3. Check candidate/shared akmods cache: [`ci_tools/main_check_candidate_akmods_cache.py`](../ci_tools/main_check_candidate_akmods_cache.py)
4. Clone pinned akmods source: [`ci_tools/akmods_clone_pinned.py`](../ci_tools/akmods_clone_pinned.py)
5. Configure akmods target image path: [`ci_tools/akmods_configure_zfs_target.py`](../ci_tools/akmods_configure_zfs_target.py)
6. Build/publish akmods image: [`ci_tools/akmods_build_and_publish.py`](../ci_tools/akmods_build_and_publish.py)
7. Publish candidate akmods alias tags: [`ci_tools/main_publish_candidate_akmods_alias.py`](../ci_tools/main_publish_candidate_akmods_alias.py)
8. Rewrite recipe/container inputs for candidate build: [`ci_tools/main_configure_candidate_recipe.py`](../ci_tools/main_configure_candidate_recipe.py)
9. Promote candidate to stable tags: [`ci_tools/main_promote_stable.py`](../ci_tools/main_promote_stable.py)

### 4. Branch Workflow Modules (Read In Job Order)

Read these in this sequence to match `build-beta.yml`:

1. Compute branch-safe tag parts: [`ci_tools/beta_compute_branch_metadata.py`](../ci_tools/beta_compute_branch_metadata.py)
2. Detect Fedora version from base stream: [`ci_tools/beta_detect_fedora_version.py`](../ci_tools/beta_detect_fedora_version.py)
3. Check shared akmods availability: [`ci_tools/beta_check_branch_akmods_cache.py`](../ci_tools/beta_check_branch_akmods_cache.py)
4. Publish branch alias tag in candidate repo: [`ci_tools/beta_publish_branch_akmods_alias.py`](../ci_tools/beta_publish_branch_akmods_alias.py)
5. Rewrite recipe for branch alias source: [`ci_tools/beta_configure_branch_recipe.py`](../ci_tools/beta_configure_branch_recipe.py)

### 5. Build Inputs Used By Python Modules

Read these next so you can connect Python edits to actual build files:

1. Recipe file rewritten during runs: [`recipes/recipe.yml`](../recipes/recipe.yml)
2. Akmods containerfile rewritten during runs: [`containerfiles/zfs-akmods/Containerfile`](../containerfiles/zfs-akmods/Containerfile)
3. Optional lock replay file: [`ci/inputs.lock.json`](../ci/inputs.lock.json)

### 6. Tests (How Logic Is Verified)

Read tests last to confirm expected behavior:

1. Command dispatch checks: [`tests/test_cli.py`](../tests/test_cli.py)
2. Input resolution behavior: [`tests/test_main_resolve_build_inputs.py`](../tests/test_main_resolve_build_inputs.py)
3. Candidate alias behavior: [`tests/test_main_publish_candidate_akmods_alias.py`](../tests/test_main_publish_candidate_akmods_alias.py)
4. Akmods build env behavior: [`tests/test_akmods_build_and_publish.py`](../tests/test_akmods_build_and_publish.py)
5. Branch metadata behavior: [`tests/test_beta_compute_branch_metadata.py`](../tests/test_beta_compute_branch_metadata.py)

## Trace One Value End-To-End (`kernel_release`)

If you want to practice reading code flow, trace `kernel_release`:

1. Resolved in [`ci_tools/main_resolve_build_inputs.py`](../ci_tools/main_resolve_build_inputs.py).
2. Written to step outputs (`GITHUB_OUTPUT`) and consumed by later jobs.
3. Used for akmods cache checks and kernel-matched tag names.
4. Used when rewriting recipe/container inputs before candidate compose.

This single value is a good way to see how data moves across jobs and files.

## Practical Tip

When reading any module:

1. Start at `main()` to see required environment variables.
2. Follow helper calls in order.
3. Match print/error messages to workflow logs so you can debug runs quickly.
