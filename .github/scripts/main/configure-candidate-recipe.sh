#!/usr/bin/env bash
# Script: main/configure-candidate-recipe.sh
# What: Rewrites recipe and ZFS containerfile references for the candidate image build.
# Doing: Leaves recipe image/base fields unchanged and points `AKMODS_IMAGE` to a kernel-matched cache tag.
# Why: BlueBuild derives base reference from `base-image` + `image-version`; only akmods source should be rewritten here.
# Goal: Produce a candidate build configuration that pulls akmods matching the resolved base kernel.
set -euo pipefail

# Normalize owner for OCI registry paths.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
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

# Point ZFS install logic to a kernel-specific akmods tag to avoid rolling-tag drift.
sed -i -E "s#^AKMODS_IMAGE=.*#AKMODS_IMAGE=\"ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-\\\${FEDORA_VERSION}-${KERNEL_RELEASE}\"#" "${ZFS_CONTAINERFILE}"

# Print effective values for traceability in workflow logs.
grep -n '^base-image:' recipes/recipe.yml
grep -n '^image-version:' recipes/recipe.yml
grep -n '^AKMODS_IMAGE=' "${ZFS_CONTAINERFILE}"
