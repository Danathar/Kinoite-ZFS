#!/usr/bin/env bash
# Script: akmods/clone-pinned-akmods.sh
# What: Fetches a pinned commit of the akmods tooling into /tmp/akmods.
# Doing: Recreates /tmp/akmods, fetches only `AKMODS_UPSTREAM_REF`, checks out detached HEAD, verifies SHA.
# Why: Prevents floating-upstream drift and guarantees the build uses the intended audited source.
# Goal: Prepare a deterministic akmods source tree for subsequent configure/build steps.
set -euo pipefail

# Start from a clean, deterministic workspace each run.
rm -rf /tmp/akmods
mkdir -p /tmp/akmods
cd /tmp/akmods

# Clone only the pinned commit instead of floating branches.
# This prevents upstream drift from changing behavior between runs.
git init .
git remote add origin "${AKMODS_UPSTREAM_REPO}"
git fetch --depth 1 origin "${AKMODS_UPSTREAM_REF}"
git checkout --detach FETCH_HEAD

# Defense-in-depth: verify the resolved commit exactly matches requested pin.
resolved_ref="$(git rev-parse HEAD)"
if [[ "${resolved_ref}" != "${AKMODS_UPSTREAM_REF}" ]]; then
  echo "Pinned ref mismatch: expected ${AKMODS_UPSTREAM_REF}, got ${resolved_ref}" >&2
  exit 1
fi

echo "Using pinned akmods ref: ${resolved_ref}"
