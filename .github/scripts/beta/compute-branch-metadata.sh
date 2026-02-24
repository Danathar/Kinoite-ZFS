#!/usr/bin/env bash
set -euo pipefail

# Source branch name from GitHub context.
branch="${GITHUB_REF_NAME}"

# Sanitize to characters accepted by OCI tags/repository paths:
# - lowercase
# - replace unsupported characters with '-'
# - trim leading/trailing separators
safe="$(echo "${branch}" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's#[^a-z0-9._-]+#-#g; s#^-+##; s#-+$##')"

# Final fallback if sanitization collapses to empty.
if [[ -z "${safe}" ]]; then
  safe="branch"
fi

# Build branch image tag. Prefix helps visually distinguish branch artifacts.
image_tag="beta-${safe}"
# Keep within conservative length bounds for registry/path compatibility.
image_tag="${image_tag:0:120}"
image_tag="${image_tag%-}"

# Build branch-specific akmods repo name.
akmods_repo="akmods-zfs-${safe}"
akmods_repo="${akmods_repo:0:120}"
akmods_repo="${akmods_repo%-}"

# Defensive defaults after truncation/cleanup.
if [[ -z "${image_tag}" ]]; then
  image_tag="beta-branch"
fi
if [[ -z "${akmods_repo}" ]]; then
  akmods_repo="akmods-zfs-branch"
fi

# Publish outputs for downstream jobs in this workflow.
{
  echo "image_tag=${image_tag}"
  echo "akmods_repo=${akmods_repo}"
} >> "${GITHUB_OUTPUT}"

# Log effective values for troubleshooting.
echo "Branch image tag: ${image_tag}"
echo "Branch akmods repo: ${akmods_repo}"
