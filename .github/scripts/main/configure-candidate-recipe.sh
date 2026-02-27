#!/usr/bin/env bash
# Script: main/configure-candidate-recipe.sh
# What: Rewrites recipe and ZFS containerfile references for the candidate image build.
# Doing: Pins `base-image`/`image-version` to the resolved immutable base tag and points `AKMODS_IMAGE` to a kernel-matched cache tag.
# Why: Prevents cross-job drift when floating `latest` advances between akmods and candidate image jobs.
# Goal: Produce a candidate build configuration that uses one coherent base+akmods kernel input set.
set -euo pipefail

# Normalize owner for OCI registry paths.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
RECIPE_FILE="recipes/recipe.yml"
# ZFS install logic is externalized to this containerfile snippet.
ZFS_CONTAINERFILE="containerfiles/zfs-akmods/Containerfile"

# Workflow passes the resolved base kernel release; require it for kernel-specific akmods tag selection.
if [[ -z "${KERNEL_RELEASE:-}" ]]; then
  echo "KERNEL_RELEASE is required" >&2
  exit 1
fi
if [[ -z "${AKMODS_REPO:-}" ]]; then
  echo "AKMODS_REPO is required" >&2
  exit 1
fi
if [[ -z "${BASE_IMAGE_NAME:-}" ]]; then
  echo "BASE_IMAGE_NAME is required" >&2
  exit 1
fi
if [[ -z "${BASE_IMAGE_TAG:-}" ]]; then
  echo "BASE_IMAGE_TAG is required" >&2
  exit 1
fi

# Pin recipe base image tag to the resolved immutable build tag.
sed -i -E "s#^base-image:.*#base-image: ${BASE_IMAGE_NAME}#" "${RECIPE_FILE}"
sed -i -E "s#^image-version:.*#image-version: ${BASE_IMAGE_TAG}#" "${RECIPE_FILE}"

# Point ZFS install logic to a kernel-specific akmods tag to avoid rolling-tag drift.
sed -i -E "s#^AKMODS_IMAGE=.*#AKMODS_IMAGE=\"ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-\\\${FEDORA_VERSION}-${KERNEL_RELEASE}\"#" "${ZFS_CONTAINERFILE}"

# Print effective values for traceability in workflow logs.
grep -n '^base-image:' "${RECIPE_FILE}"
grep -n '^image-version:' "${RECIPE_FILE}"
grep -n '^AKMODS_IMAGE=' "${ZFS_CONTAINERFILE}"
