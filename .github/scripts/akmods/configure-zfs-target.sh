#!/usr/bin/env bash
set -euo pipefail

# Modify the cloned akmods source in-place.
cd /tmp/akmods
# Normalize repository owner for OCI path compatibility in GHCR.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"

# Export variables consumed by yq's strenv() calls below.
export FEDORA_VERSION IMAGE_ORG AKMODS_REPO AKMODS_DESCRIPTION

# Inject (or replace) the zfs target mapping for the selected Fedora major stream.
# This tells akmods tooling where to publish the cache image for this run.
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
