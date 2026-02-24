#!/usr/bin/env bash
set -euo pipefail

# Normalize owner for OCI registry paths.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
# ZFS install logic is externalized to this containerfile snippet.
ZFS_CONTAINERFILE="containerfiles/zfs-akmods/Containerfile"

# Candidate job publishes to dedicated candidate image tag.
sed -i -E "s/^image-version:.*/image-version: ${IMAGE_TAG}/" recipes/recipe.yml
# Pin base image by digest resolved in input step for per-run determinism.
sed -i -E "s#^base-image:.*#base-image: ${BASE_IMAGE_PINNED}#" recipes/recipe.yml
# Point ZFS install logic to candidate akmods cache repo for this run.
sed -i -E "s#^AKMODS_IMAGE=.*#AKMODS_IMAGE=\"ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-\\\${FEDORA_VERSION}\"#" "${ZFS_CONTAINERFILE}"

# Print effective values for traceability in workflow logs.
grep -n '^base-image:' recipes/recipe.yml
grep -n '^image-version:' recipes/recipe.yml
grep -n '^AKMODS_IMAGE=' "${ZFS_CONTAINERFILE}"
