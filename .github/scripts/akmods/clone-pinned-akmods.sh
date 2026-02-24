#!/usr/bin/env bash
set -euo pipefail

rm -rf /tmp/akmods
mkdir -p /tmp/akmods
cd /tmp/akmods

git init .
git remote add origin "${AKMODS_UPSTREAM_REPO}"
git fetch --depth 1 origin "${AKMODS_UPSTREAM_REF}"
git checkout --detach FETCH_HEAD

resolved_ref="$(git rev-parse HEAD)"
if [[ "${resolved_ref}" != "${AKMODS_UPSTREAM_REF}" ]]; then
  echo "Pinned ref mismatch: expected ${AKMODS_UPSTREAM_REF}, got ${resolved_ref}" >&2
  exit 1
fi

echo "Using pinned akmods ref: ${resolved_ref}"
