#!/usr/bin/env bash
# Script: main/configure-candidate-recipe.sh
# What: Updates recipe and ZFS containerfile values before the candidate image build.
# Doing: Sets `base-image`/`image-version` to a fixed tag for this run and sets `AKMODS_IMAGE` to the matching kernel tag.
# Why: Keeps the base image and akmods source in sync even if moving tags update during the workflow.
# Goal: Build the candidate image from one consistent input set.
set -euo pipefail

# Normalize owner for OCI registry paths.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
RECIPE_FILE="recipes/recipe.yml"
# ZFS install logic is externalized to this containerfile snippet.
ZFS_CONTAINERFILE="containerfiles/zfs-akmods/Containerfile"

# These values come from earlier workflow steps and are required.
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

# Pin recipe base image tag for this run.
sed -i -E "s#^base-image:.*#base-image: ${BASE_IMAGE_NAME}#" "${RECIPE_FILE}"
sed -i -E "s#^image-version:.*#image-version: ${BASE_IMAGE_TAG}#" "${RECIPE_FILE}"

# Point ZFS install logic to the kernel-specific akmods tag.
sed -i -E "s#^AKMODS_IMAGE=.*#AKMODS_IMAGE=\"ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-\\\${FEDORA_VERSION}-${KERNEL_RELEASE}\"#" "${ZFS_CONTAINERFILE}"

# Print final values in logs for quick debugging.
grep -n '^base-image:' "${RECIPE_FILE}"
grep -n '^image-version:' "${RECIPE_FILE}"
grep -n '^AKMODS_IMAGE=' "${ZFS_CONTAINERFILE}"
