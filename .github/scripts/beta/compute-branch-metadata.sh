#!/usr/bin/env bash
set -euo pipefail

branch="${GITHUB_REF_NAME}"

safe="$(echo "${branch}" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's#[^a-z0-9._-]+#-#g; s#^-+##; s#-+$##')"

if [[ -z "${safe}" ]]; then
  safe="branch"
fi

image_tag="beta-${safe}"
image_tag="${image_tag:0:120}"
image_tag="${image_tag%-}"

akmods_repo="akmods-zfs-${safe}"
akmods_repo="${akmods_repo:0:120}"
akmods_repo="${akmods_repo%-}"

if [[ -z "${image_tag}" ]]; then
  image_tag="beta-branch"
fi
if [[ -z "${akmods_repo}" ]]; then
  akmods_repo="akmods-zfs-branch"
fi

{
  echo "image_tag=${image_tag}"
  echo "akmods_repo=${akmods_repo}"
} >> "${GITHUB_OUTPUT}"

echo "Branch image tag: ${image_tag}"
echo "Branch akmods repo: ${akmods_repo}"
