#!/usr/bin/env bash
set -euo pipefail

cd /tmp/akmods
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"

export FEDORA_VERSION IMAGE_ORG AKMODS_REPO AKMODS_DESCRIPTION

yq -i '
  .images[strenv(FEDORA_VERSION)].main.zfs = {
    "org": strenv(IMAGE_ORG),
    "registry": "ghcr.io",
    "repo": "akmods",
    "transport": "docker://",
    "name": strenv(AKMODS_REPO),
    "description": strenv(AKMODS_DESCRIPTION),
    "architecture": ["x86_64"]
  }
' images.yaml
