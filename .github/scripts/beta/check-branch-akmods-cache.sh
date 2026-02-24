#!/usr/bin/env bash
set -euo pipefail

IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
AKMODS_IMAGE="ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-${FEDORA_VERSION}"

if skopeo inspect "docker://${AKMODS_IMAGE}" >/dev/null 2>&1; then
  workdir="$(mktemp -d)"
  trap 'rm -rf "${workdir}"' EXIT
  skopeo copy --retry-times 3 "docker://${AKMODS_IMAGE}" "dir:${workdir}/akmods" >/dev/null
  mapfile -t layer_files < <(
    jq -r '.layers[]?.digest // empty' "${workdir}/akmods/manifest.json" \
      | sed -E "s#^sha256:#${workdir}/akmods/#"
  )
  for layer in "${layer_files[@]}"; do
    tar -xf "${layer}" -C "${workdir}"
  done

  if find "${workdir}/rpms/kmods/zfs" -maxdepth 1 -type f -name "kmod-zfs-${KERNEL_RELEASE}-*.rpm" | grep -q .; then
    echo "exists=true" >> "${GITHUB_OUTPUT}"
    echo "Found matching ${AKMODS_IMAGE} kmod for kernel ${KERNEL_RELEASE}; akmods rebuild can be skipped."
  else
    echo "exists=false" >> "${GITHUB_OUTPUT}"
    echo "Cached ${AKMODS_IMAGE} is present but missing kmod for kernel ${KERNEL_RELEASE}; akmods rebuild is required."
  fi
else
  echo "exists=false" >> "${GITHUB_OUTPUT}"
  echo "No existing ${AKMODS_IMAGE}; akmods rebuild is required."
fi
