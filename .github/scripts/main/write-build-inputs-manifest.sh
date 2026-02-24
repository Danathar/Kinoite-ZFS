#!/usr/bin/env bash
# Script: main/write-build-inputs-manifest.sh
# What: Writes a machine-readable build-input manifest artifact for replay, audit, and debugging.
# Doing: Collects workflow/run metadata plus resolved pinned inputs and renders `artifacts/build-inputs.json`.
# Why: Preserves exact provenance for each build so failures can be diagnosed and builds can be replayed safely.
# Goal: Persist a complete input record that documents what was built, from which pinned sources, and when.
set -euo pipefail

# Store a per-run manifest used for replay/debugging.
mkdir -p artifacts

# Build structured JSON from step/job context and resolved input values.
# Values are passed via env so this script remains workflow-expression agnostic.
jq -n \
  --arg schema_version "1" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg repository "${GITHUB_REPOSITORY}" \
  --arg workflow "${GITHUB_WORKFLOW}" \
  --arg run_id "${GITHUB_RUN_ID}" \
  --arg run_attempt "${GITHUB_RUN_ATTEMPT}" \
  --arg run_number "${GITHUB_RUN_NUMBER}" \
  --arg git_ref "${GITHUB_REF}" \
  --arg git_sha "${GITHUB_SHA}" \
  --arg actor "${GITHUB_ACTOR}" \
  --arg fedora_version "${FEDORA_VERSION}" \
  --arg kernel_release "${KERNEL_RELEASE}" \
  --arg base_image_ref "${BASE_IMAGE_REF}" \
  --arg base_image_pinned "${BASE_IMAGE_PINNED}" \
  --arg base_image_digest "${BASE_IMAGE_DIGEST}" \
  --arg build_container_ref "${BUILD_CONTAINER_REF}" \
  --arg build_container_pinned "${BUILD_CONTAINER_PINNED}" \
  --arg build_container_digest "${BUILD_CONTAINER_DIGEST}" \
  --arg zfs_minor_version "${ZFS_MINOR_VERSION}" \
  --arg akmods_upstream_ref "${AKMODS_UPSTREAM_REF}" \
  --arg use_input_lock "${USE_INPUT_LOCK}" \
  --arg lock_file_path "${LOCK_FILE_PATH}" \
  '{
    schema_version: ($schema_version | tonumber),
    generated_at,
    repository,
    workflow,
    run: {
      id: ($run_id | tonumber),
      attempt: ($run_attempt | tonumber),
      number: ($run_number | tonumber),
      ref: $git_ref,
      sha: $git_sha,
      actor: $actor
    },
    inputs: {
      use_input_lock: ($use_input_lock == "true"),
      lock_file_path,
      fedora_version,
      kernel_release,
      base_image_ref,
      base_image_pinned,
      base_image_digest,
      build_container_ref,
      build_container_pinned,
      build_container_digest,
      zfs_minor_version,
      akmods_upstream_ref
    }
  }' > artifacts/build-inputs.json

# Print manifest content for log visibility and easy copy into lock file updates.
cat artifacts/build-inputs.json
