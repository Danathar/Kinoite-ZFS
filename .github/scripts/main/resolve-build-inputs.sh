#!/usr/bin/env bash
# Script: main/resolve-build-inputs.sh
# What: Resolves and validates the build inputs (base image, build container, ZFS, akmods ref) for this run.
# Doing: Loads lock replay values or defaults, enforces consistency checks, pins image refs to immutable digests.
# Why: Prevents accidental drift and guarantees downstream jobs use reproducible, explicit build inputs.
# Goal: Emit authoritative pinned inputs and metadata consumed by candidate-akmods and candidate-image jobs.
set -euo pipefail

# Inputs are passed from workflow env so this script stays reusable and testable.
use_input_lock="${USE_INPUT_LOCK}"
lock_file_path="${LOCK_FILE}"
build_container_ref="${BUILD_CONTAINER_REF}"

# Two modes:
# - lock replay mode: pull pinned values from lock file
# - latest mode: use configured defaults
if [[ "${use_input_lock}" == "true" ]]; then
  # Replay mode requires a present lock file.
  if [[ ! -f "${lock_file_path}" ]]; then
    echo "Replay lock file not found: ${lock_file_path}" >&2
    exit 1
  fi

  # Read optional/required inputs from lock file.
  base_image_ref="$(jq -r '.base_image // empty' "${lock_file_path}")"
  lock_build_container_ref="$(jq -r '.build_container // empty' "${lock_file_path}")"
  zfs_minor_version="$(jq -r '.zfs_minor_version // empty' "${lock_file_path}")"
  akmods_upstream_ref="$(jq -r '.akmods_upstream_ref // empty' "${lock_file_path}")"

  # Validate required and placeholder values for replay safety.
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

  # Enforce that workflow-provided build container matches lock file when both are set.
  if [[ -n "${lock_build_container_ref}" && "${build_container_ref}" != "${lock_build_container_ref}" ]]; then
    echo "Replay mismatch: build container input (${build_container_ref}) does not match lock file (${lock_build_container_ref})." >&2
    echo "Set workflow input build_container_image=${lock_build_container_ref} when use_input_lock=true." >&2
    exit 1
  fi

  # Backfill optional lock fields from defaults for compatibility.
  if [[ -z "${zfs_minor_version}" ]]; then
    zfs_minor_version="${DEFAULT_ZFS_MINOR_VERSION}"
  fi
  if [[ -z "${akmods_upstream_ref}" ]]; then
    akmods_upstream_ref="${DEFAULT_AKMODS_REF}"
  fi
else
  # Latest mode follows configured floating defaults.
  base_image_ref="${DEFAULT_BASE_IMAGE}"
  zfs_minor_version="${DEFAULT_ZFS_MINOR_VERSION}"
  akmods_upstream_ref="${DEFAULT_AKMODS_REF}"
fi

# Resolve base image metadata to immutable digest + kernel label.
base_inspect_json="$(skopeo inspect "docker://${base_image_ref}")"
base_image_name="$(jq -r '.Name // empty' <<< "${base_inspect_json}")"
base_image_digest="$(jq -r '.Digest // empty' <<< "${base_inspect_json}")"
kernel_release="$(jq -r '.Labels["ostree.linux"] // empty' <<< "${base_inspect_json}")"
base_image_version_label="$(jq -r '.Labels["org.opencontainers.image.version"] // empty' <<< "${base_inspect_json}")"

# Ensure base image resolution succeeded and exposed required kernel label.
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

# Build immutable base reference (<name>@<digest>) for deterministic downstream usage.
base_image_pinned="${base_image_name}@${base_image_digest}"

# Derive an immutable base tag that resolves to the same digest as `base_image_pinned`.
# This is required because BlueBuild consumes `base-image` + `image-version` (name:tag),
# not digest references, when generating the Containerfile.
base_ref_source_tag=""
if [[ "${base_image_ref}" =~ ^[^@]+:([^/@]+)$ ]]; then
  base_ref_source_tag="${BASH_REMATCH[1]}"
fi

# If input already uses a date-stamped tag, keep it.
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

# Verify the selected tag resolves to the same digest as the originally resolved base input.
selected_tag_digest="$(skopeo inspect "docker://${base_image_name}:${base_image_tag}" | jq -r '.Digest // empty')"
if [[ "${selected_tag_digest}" != "${base_image_digest}" ]]; then
  echo "Resolved tag ${base_image_name}:${base_image_tag} does not match digest ${base_image_digest}" >&2
  exit 1
fi

# Resolve build container metadata to immutable digest for replay/audit records.
container_inspect_json="$(skopeo inspect "docker://${build_container_ref}")"
build_container_name="$(jq -r '.Name // empty' <<< "${container_inspect_json}")"
build_container_digest="$(jq -r '.Digest // empty' <<< "${container_inspect_json}")"

# Ensure build container reference resolved correctly.
if [[ -z "${build_container_name}" || -z "${build_container_digest}" ]]; then
  echo "Failed to resolve build container digest for ${build_container_ref}" >&2
  exit 1
fi

build_container_pinned="${build_container_name}@${build_container_digest}"

# Emit outputs for downstream workflow steps.
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

# Human-readable summary in logs for quick triage.
echo "Resolved base image: ${base_image_pinned}"
echo "Resolved base image tag: ${base_image_name}:${base_image_tag}"
echo "Resolved build container: ${build_container_pinned}"
echo "Kernel release: ${kernel_release}"
echo "Fedora version: ${fedora_version}"
echo "ZFS minor version: ${zfs_minor_version}"
