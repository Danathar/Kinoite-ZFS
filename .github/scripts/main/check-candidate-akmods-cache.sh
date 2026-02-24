#!/usr/bin/env bash
set -euo pipefail

# Build candidate and stable cache references for the current Fedora major stream.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
candidate_akmods_image="ghcr.io/${IMAGE_ORG}/${CANDIDATE_AKMODS_REPO}:main-${FEDORA_VERSION}"
stable_akmods_image="ghcr.io/${IMAGE_ORG}/${STABLE_AKMODS_REPO}:main-${FEDORA_VERSION}"

# Prefer candidate cache. Fall back to stable cache for compatibility with older publish paths.
akmods_image=""
if skopeo inspect "docker://${candidate_akmods_image}" >/dev/null 2>&1; then
  akmods_image="${candidate_akmods_image}"
  echo "Using candidate cache source ${akmods_image}"
elif [[ "${STABLE_AKMODS_REPO}" != "${CANDIDATE_AKMODS_REPO}" ]] && skopeo inspect "docker://${stable_akmods_image}" >/dev/null 2>&1; then
  akmods_image="${stable_akmods_image}"
  echo "Candidate cache tag missing; falling back to stable cache source ${akmods_image}"
fi

# Validate whether selected cache contains a kmod for the exact base kernel release.
if [[ -n "${akmods_image}" ]]; then
  # Pull the cache image into local dir: layout to inspect layer contents directly.
  workdir="$(mktemp -d)"
  trap 'rm -rf "${workdir}"' EXIT
  skopeo copy --retry-times 3 "docker://${akmods_image}" "dir:${workdir}/akmods" >/dev/null

  # Expand manifest layers so packaged RPM files are available on disk.
  mapfile -t layer_files < <(
    jq -r '.layers[]?.digest // empty' "${workdir}/akmods/manifest.json" \
      | sed -E "s#^sha256:#${workdir}/akmods/#"
  )
  for layer in "${layer_files[@]}"; do
    tar -xf "${layer}" -C "${workdir}"
  done

  # Emit `exists=true` only if cache has a kernel-matching kmod RPM.
  if find "${workdir}/rpms/kmods/zfs" -maxdepth 1 -type f -name "kmod-zfs-${KERNEL_RELEASE}-*.rpm" | grep -q .; then
    echo "exists=true" >> "${GITHUB_OUTPUT}"
    echo "Found matching ${akmods_image} kmod for kernel ${KERNEL_RELEASE}; akmods rebuild can be skipped."
  else
    echo "exists=false" >> "${GITHUB_OUTPUT}"
    echo "Cached ${akmods_image} is present but missing kmod for kernel ${KERNEL_RELEASE}; akmods rebuild is required."
  fi
else
  # No cache path available: force rebuild.
  echo "exists=false" >> "${GITHUB_OUTPUT}"
  echo "No existing candidate/stable akmods cache image for Fedora ${FEDORA_VERSION}; akmods rebuild is required."
fi
