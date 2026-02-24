#!/usr/bin/env bash
set -euo pipefail

# Normalize owner for OCI repository references.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"

# BlueBuild emits a deterministic commit+Fedora tag (e.g., a1b2c3d-43).
# Resolve that tag to digest so stable tags point at a fixed immutable artifact.
candidate_source_tag="${GITHUB_SHA::7}-${FEDORA_VERSION}"
candidate_image_by_tag="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}:${candidate_source_tag}"
candidate_image_digest="$(skopeo inspect \
  --creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  --format '{{.Digest}}' \
  "${candidate_image_by_tag}")"

# Hard fail if candidate image is missing to avoid promoting stale images.
if [[ -z "${candidate_image_digest}" ]]; then
  echo "Failed to resolve candidate image digest from ${candidate_image_by_tag}" >&2
  exit 1
fi

# Promotion destinations:
# - latest: active stable stream
# - stable-<run>-<sha>: immutable audit/rollback reference
candidate_image="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}@${candidate_image_digest}"
stable_image="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}:latest"
audit_image="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}:stable-${GITHUB_RUN_NUMBER}-${GITHUB_SHA::7}"

# Candidate and stable akmods references for the same Fedora major stream.
candidate_akmods="docker://ghcr.io/${IMAGE_ORG}/${CANDIDATE_AKMODS_REPO}:main-${FEDORA_VERSION}"
stable_akmods="docker://ghcr.io/${IMAGE_ORG}/${STABLE_AKMODS_REPO}:main-${FEDORA_VERSION}"

# Promote candidate OS image to stable latest.
skopeo copy --retry-times 3 \
  --src-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  --dest-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  "${candidate_image}" "${stable_image}"

# Publish immutable audit tag pointing to same promoted digest.
skopeo copy --retry-times 3 \
  --src-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  --dest-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  "${candidate_image}" "${audit_image}"

# Promote akmods cache:
# - prefer candidate cache
# - fallback to stable cache when candidate tag is absent (compat path)
if skopeo inspect --creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" "${candidate_akmods}" >/dev/null 2>&1; then
  source_akmods="${candidate_akmods}"
elif skopeo inspect --creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" "${stable_akmods}" >/dev/null 2>&1; then
  source_akmods="${stable_akmods}"
  echo "Candidate akmods tag missing; using stable akmods tag as promotion source."
else
  echo "Neither candidate nor stable akmods tag exists for Fedora ${FEDORA_VERSION}." >&2
  exit 1
fi

# Skip copy if source and destination are already identical refs.
if [[ "${source_akmods}" != "${stable_akmods}" ]]; then
  skopeo copy --retry-times 3 \
    --src-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
    --dest-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
    "${source_akmods}" "${stable_akmods}"
else
  echo "Akmods source already at stable tag ${stable_akmods}; skipping retag copy."
fi

# Log promoted refs for auditability in job output.
echo "Resolved candidate source ${candidate_image_by_tag} -> ${candidate_image}"
echo "Promoted ${candidate_image} -> ${stable_image}"
echo "Published audit tag ${audit_image}"
echo "Promoted ${source_akmods} -> ${stable_akmods}"
