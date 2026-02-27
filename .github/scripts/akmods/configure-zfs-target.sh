#!/usr/bin/env bash
# Script: akmods/configure-zfs-target.sh
# What: Injects/updates the ZFS target mapping in akmods `images.yaml`.
# Doing: Normalizes org name (convert to lowercase) and writes target metadata via `yq` using exported env values.
# Why: Decouples publish destination logic from workflows and makes target wiring reusable.
# Goal: Ensure akmods tooling publishes ZFS artifacts to the correct GHCR repo/tag namespace.
set -euo pipefail

# Modify the cloned akmods source in-place.
cd /tmp/akmods
# Lowercase repository owner for container registry path compatibility in GHCR.
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
