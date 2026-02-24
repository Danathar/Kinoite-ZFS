#!/usr/bin/env bash
set -euo pipefail

# Branch builds isolate caches by repository name to avoid touching main caches.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
AKMODS_IMAGE="ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-${FEDORA_VERSION}"

# Fast-path: check whether a cache image already exists for this branch/Fedora stream.
if skopeo inspect "docker://${AKMODS_IMAGE}" >/dev/null 2>&1; then
  # Pull to a local dir: layout so we can inspect packaged RPM payloads.
  workdir="$(mktemp -d)"
  trap 'rm -rf "${workdir}"' EXIT
  skopeo copy --retry-times 3 "docker://${AKMODS_IMAGE}" "dir:${workdir}/akmods" >/dev/null

  # Extract only manifest-declared layers and unpack them for file-level checks.
  mapfile -t layer_files < <(
    jq -r '.layers[]?.digest // empty' "${workdir}/akmods/manifest.json" \
      | sed -E "s#^sha256:#${workdir}/akmods/#"
  )
  for layer in "${layer_files[@]}"; do
    tar -xf "${layer}" -C "${workdir}"
  done

  # Cache is reusable only when it contains a kmod built for the exact base kernel.
  if find "${workdir}/rpms/kmods/zfs" -maxdepth 1 -type f -name "kmod-zfs-${KERNEL_RELEASE}-*.rpm" | grep -q .; then
    # Emit step output consumed by workflow `if` conditions.
    echo "exists=true" >> "${GITHUB_OUTPUT}"
    echo "Found matching ${AKMODS_IMAGE} kmod for kernel ${KERNEL_RELEASE}; akmods rebuild can be skipped."
  else
    echo "exists=false" >> "${GITHUB_OUTPUT}"
    echo "Cached ${AKMODS_IMAGE} is present but missing kmod for kernel ${KERNEL_RELEASE}; akmods rebuild is required."
  fi
else
  # No branch cache yet; force rebuild path.
  echo "exists=false" >> "${GITHUB_OUTPUT}"
  echo "No existing ${AKMODS_IMAGE}; akmods rebuild is required."
fi
