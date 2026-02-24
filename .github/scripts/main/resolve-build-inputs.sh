#!/usr/bin/env bash
set -euo pipefail

use_input_lock="${USE_INPUT_LOCK}"
lock_file_path="${LOCK_FILE}"
build_container_ref="${BUILD_CONTAINER_REF}"

if [[ "${use_input_lock}" == "true" ]]; then
  if [[ ! -f "${lock_file_path}" ]]; then
    echo "Replay lock file not found: ${lock_file_path}" >&2
    exit 1
  fi

  base_image_ref="$(jq -r '.base_image // empty' "${lock_file_path}")"
  lock_build_container_ref="$(jq -r '.build_container // empty' "${lock_file_path}")"
  zfs_minor_version="$(jq -r '.zfs_minor_version // empty' "${lock_file_path}")"
  akmods_upstream_ref="$(jq -r '.akmods_upstream_ref // empty' "${lock_file_path}")"

  if [[ -z "${base_image_ref}" ]]; then
    echo "Lock file missing required field: base_image" >&2
    exit 1
  fi
  if [[ "${base_image_ref}" == *REPLACE_ME* ]]; then
    echo "Lock file base_image still contains placeholder value" >&2
    exit 1
  fi
  if [[ -n "${lock_build_container_ref}" && "${lock_build_container_ref}" == *REPLACE_ME* ]]; then
    echo "Lock file build_container still contains placeholder value" >&2
    exit 1
  fi

  if [[ -n "${lock_build_container_ref}" && "${build_container_ref}" != "${lock_build_container_ref}" ]]; then
    echo "Replay mismatch: build container input (${build_container_ref}) does not match lock file (${lock_build_container_ref})." >&2
    echo "Set workflow input build_container_image=${lock_build_container_ref} when use_input_lock=true." >&2
    exit 1
  fi

  if [[ -z "${zfs_minor_version}" ]]; then
    zfs_minor_version="${DEFAULT_ZFS_MINOR_VERSION}"
  fi
  if [[ -z "${akmods_upstream_ref}" ]]; then
    akmods_upstream_ref="${DEFAULT_AKMODS_REF}"
  fi
else
  base_image_ref="${DEFAULT_BASE_IMAGE}"
  zfs_minor_version="${DEFAULT_ZFS_MINOR_VERSION}"
  akmods_upstream_ref="${DEFAULT_AKMODS_REF}"
fi

base_inspect_json="$(skopeo inspect "docker://${base_image_ref}")"
base_image_name="$(jq -r '.Name // empty' <<< "${base_inspect_json}")"
base_image_digest="$(jq -r '.Digest // empty' <<< "${base_inspect_json}")"
kernel_release="$(jq -r '.Labels["ostree.linux"] // empty' <<< "${base_inspect_json}")"

if [[ -z "${base_image_name}" || -z "${base_image_digest}" ]]; then
  echo "Failed to resolve base image digest for ${base_image_ref}" >&2
  exit 1
fi
if [[ -z "${kernel_release}" ]]; then
  echo "Failed to read ostree.linux label from ${base_image_ref}" >&2
  exit 1
fi

fedora_version="$(sed -E 's/.*fc([0-9]+).*/\1/' <<< "${kernel_release}")"
if [[ -z "${fedora_version}" ]]; then
  echo "Failed to extract Fedora version from kernel release ${kernel_release}" >&2
  exit 1
fi

base_image_pinned="${base_image_name}@${base_image_digest}"

container_inspect_json="$(skopeo inspect "docker://${build_container_ref}")"
build_container_name="$(jq -r '.Name // empty' <<< "${container_inspect_json}")"
build_container_digest="$(jq -r '.Digest // empty' <<< "${container_inspect_json}")"

if [[ -z "${build_container_name}" || -z "${build_container_digest}" ]]; then
  echo "Failed to resolve build container digest for ${build_container_ref}" >&2
  exit 1
fi

build_container_pinned="${build_container_name}@${build_container_digest}"

{
  echo "version=${fedora_version}"
  echo "kernel_release=${kernel_release}"
  echo "base_image_ref=${base_image_ref}"
  echo "base_image_pinned=${base_image_pinned}"
  echo "base_image_digest=${base_image_digest}"
  echo "build_container_ref=${build_container_ref}"
  echo "build_container_pinned=${build_container_pinned}"
  echo "build_container_digest=${build_container_digest}"
  echo "zfs_minor_version=${zfs_minor_version}"
  echo "akmods_upstream_ref=${akmods_upstream_ref}"
  echo "use_input_lock=${use_input_lock}"
  echo "lock_file_path=${lock_file_path}"
} >> "${GITHUB_OUTPUT}"

echo "Resolved base image: ${base_image_pinned}"
echo "Resolved build container: ${build_container_pinned}"
echo "Kernel release: ${kernel_release}"
echo "Fedora version: ${fedora_version}"
echo "ZFS minor version: ${zfs_minor_version}"
