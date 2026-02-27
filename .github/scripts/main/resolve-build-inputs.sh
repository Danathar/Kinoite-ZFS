#!/usr/bin/env bash
# Script: main/resolve-build-inputs.sh
# What: Picks and validates the exact image inputs for this workflow run.
# Doing: Reads lock-file values (if enabled) or defaults, validates them, and resolves exact image digests/tags.
# Why: Keeps every job in this run aligned to the same base and builder inputs.
# Goal: Export trusted input values that later jobs can reuse.
set -euo pipefail

# Workflow values are passed through env so this script can be reused from multiple steps.
use_input_lock="${USE_INPUT_LOCK}"
lock_file_path="${LOCK_FILE}"
build_container_ref="${BUILD_CONTAINER_REF}"

# Two modes:
# - lock replay mode: use values from the lock file
# - latest mode: use configured defaults
if [[ "${use_input_lock}" == "true" ]]; then
  # Lock mode requires a present lock file.
  if [[ ! -f "${lock_file_path}" ]]; then
    echo "Replay lock file not found: ${lock_file_path}" >&2
    exit 1
  fi

  # Read optional/required inputs from lock file.
  base_image_ref="$(jq -r '.base_image // empty' "${lock_file_path}")"
  lock_build_container_ref="$(jq -r '.build_container // empty' "${lock_file_path}")"
  zfs_minor_version="$(jq -r '.zfs_minor_version // empty' "${lock_file_path}")"
  akmods_upstream_ref="$(jq -r '.akmods_upstream_ref // empty' "${lock_file_path}")"

  # Validate required fields and block placeholder values.
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

  # If both are set, make sure workflow input matches the lock file.
  if [[ -n "${lock_build_container_ref}" && "${build_container_ref}" != "${lock_build_container_ref}" ]]; then
    echo "Replay mismatch: build container input (${build_container_ref}) does not match lock file (${lock_build_container_ref})." >&2
    echo "Set workflow input build_container_image=${lock_build_container_ref} when use_input_lock=true." >&2
    exit 1
  fi

  # Fill optional lock fields from defaults when not provided.
  if [[ -z "${zfs_minor_version}" ]]; then
    zfs_minor_version="${DEFAULT_ZFS_MINOR_VERSION}"
  fi
  if [[ -z "${akmods_upstream_ref}" ]]; then
    akmods_upstream_ref="${DEFAULT_AKMODS_REF}"
  fi
else
  # Default mode follows configured moving tags.
  base_image_ref="${DEFAULT_BASE_IMAGE}"
  zfs_minor_version="${DEFAULT_ZFS_MINOR_VERSION}"
  akmods_upstream_ref="${DEFAULT_AKMODS_REF}"
fi

# Resolve base image metadata (digest + kernel label).
base_inspect_json="$(skopeo inspect "docker://${base_image_ref}")"
base_image_name="$(jq -r '.Name // empty' <<< "${base_inspect_json}")"
base_image_digest="$(jq -r '.Digest // empty' <<< "${base_inspect_json}")"
kernel_release="$(jq -r '.Labels["ostree.linux"] // empty' <<< "${base_inspect_json}")"
base_image_version_label="$(jq -r '.Labels["org.opencontainers.image.version"] // empty' <<< "${base_inspect_json}")"

# Make sure the lookup succeeded and includes the kernel label we need.
if [[ -z "${base_image_name}" || -z "${base_image_digest}" ]]; then
  echo "Failed to resolve base image digest for ${base_image_ref}" >&2
  exit 1
fi
if [[ -z "${kernel_release}" ]]; then
  echo "Failed to read ostree.linux label from ${base_image_ref}" >&2
  exit 1
fi

# Extract Fedora major from kernel naming convention (...fc43...).
fedora_version="$(sed -E 's/.*fc([0-9]+).*/\1/' <<< "${kernel_release}")"
if [[ -z "${fedora_version}" ]]; then
  echo "Failed to extract Fedora version from kernel release ${kernel_release}" >&2
  exit 1
fi

# Build a digest-pinned base reference (<name>@<digest>) for internal checks/logging.
base_image_pinned="${base_image_name}@${base_image_digest}"

# Find a stable base tag that points to the same digest as `base_image_pinned`.
# We need a tag because BlueBuild builds from `base-image` + `image-version` (name:tag),
# not from digest references.
base_ref_source_tag=""
if [[ "${base_image_ref}" =~ ^[^@]+:([^/@]+)$ ]]; then
  base_ref_source_tag="${BASH_REMATCH[1]}"
fi

# If the input already uses a date-stamped tag, keep it.
if [[ -n "${base_ref_source_tag}" && "${base_ref_source_tag}" =~ -[0-9]{8}(\.[0-9]+)?$ ]]; then
  base_image_tag="${base_ref_source_tag}"
else
  if [[ ! "${base_image_version_label}" =~ ^[0-9]+\.[0-9]{8}(\.[0-9]+)?$ ]]; then
    echo "Failed to derive immutable base tag from org.opencontainers.image.version=${base_image_version_label} for ${base_image_ref}" >&2
    exit 1
  fi

  version_suffix="${base_image_version_label#*.}"
  candidate_tags=()
  if [[ -n "${base_ref_source_tag}" ]]; then
    candidate_tags+=("${base_ref_source_tag}-${version_suffix}")
  fi
  candidate_tags+=("latest-${version_suffix}" "${fedora_version}-${version_suffix}")

  base_image_tag=""
  for candidate_tag in "${candidate_tags[@]}"; do
    candidate_digest="$(skopeo inspect "docker://${base_image_name}:${candidate_tag}" | jq -r '.Digest // empty' 2>/dev/null || true)"
    if [[ "${candidate_digest}" == "${base_image_digest}" ]]; then
      base_image_tag="${candidate_tag}"
      break
    fi
  done

  if [[ -z "${base_image_tag}" ]]; then
    echo "Failed to map ${base_image_pinned} to an immutable tag." >&2
    echo "Tried candidate tags: ${candidate_tags[*]}" >&2
    exit 1
  fi
fi

# Double-check that the chosen tag still matches the original digest.
selected_tag_digest="$(skopeo inspect "docker://${base_image_name}:${base_image_tag}" | jq -r '.Digest // empty')"
if [[ "${selected_tag_digest}" != "${base_image_digest}" ]]; then
  echo "Resolved tag ${base_image_name}:${base_image_tag} does not match digest ${base_image_digest}" >&2
  exit 1
fi

# Resolve builder container metadata to a pinned digest.
container_inspect_json="$(skopeo inspect "docker://${build_container_ref}")"
build_container_name="$(jq -r '.Name // empty' <<< "${container_inspect_json}")"
build_container_digest="$(jq -r '.Digest // empty' <<< "${container_inspect_json}")"

# Ensure builder container lookup succeeded.
if [[ -z "${build_container_name}" || -z "${build_container_digest}" ]]; then
  echo "Failed to resolve build container digest for ${build_container_ref}" >&2
  exit 1
fi

build_container_pinned="${build_container_name}@${build_container_digest}"

# Export outputs used by later workflow steps.
{
  echo "version=${fedora_version}"
  echo "kernel_release=${kernel_release}"
  echo "base_image_ref=${base_image_ref}"
  echo "base_image_name=${base_image_name}"
  echo "base_image_tag=${base_image_tag}"
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

# Print a short summary in logs for debugging.
echo "Resolved base image: ${base_image_pinned}"
echo "Resolved base image tag: ${base_image_name}:${base_image_tag}"
echo "Resolved build container: ${build_container_pinned}"
echo "Kernel release: ${kernel_release}"
echo "Fedora version: ${fedora_version}"
echo "ZFS minor version: ${zfs_minor_version}"
