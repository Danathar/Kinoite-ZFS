#!/usr/bin/env bash
set -euo pipefail

IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"

candidate_source_tag="${GITHUB_SHA::7}-${FEDORA_VERSION}"
candidate_image_by_tag="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}:${candidate_source_tag}"
candidate_image_digest="$(skopeo inspect \
  --creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  --format '{{.Digest}}' \
  "${candidate_image_by_tag}")"

if [[ -z "${candidate_image_digest}" ]]; then
  echo "Failed to resolve candidate image digest from ${candidate_image_by_tag}" >&2
  exit 1
fi

candidate_image="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}@${candidate_image_digest}"
stable_image="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}:latest"
audit_image="docker://ghcr.io/${IMAGE_ORG}/${IMAGE_NAME}:stable-${GITHUB_RUN_NUMBER}-${GITHUB_SHA::7}"

candidate_akmods="docker://ghcr.io/${IMAGE_ORG}/${CANDIDATE_AKMODS_REPO}:main-${FEDORA_VERSION}"
stable_akmods="docker://ghcr.io/${IMAGE_ORG}/${STABLE_AKMODS_REPO}:main-${FEDORA_VERSION}"

skopeo copy --retry-times 3 \
  --src-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  --dest-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  "${candidate_image}" "${stable_image}"

skopeo copy --retry-times 3 \
  --src-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  --dest-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
  "${candidate_image}" "${audit_image}"

if skopeo inspect --creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" "${candidate_akmods}" >/dev/null 2>&1; then
  source_akmods="${candidate_akmods}"
elif skopeo inspect --creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" "${stable_akmods}" >/dev/null 2>&1; then
  source_akmods="${stable_akmods}"
  echo "Candidate akmods tag missing; using stable akmods tag as promotion source."
else
  echo "Neither candidate nor stable akmods tag exists for Fedora ${FEDORA_VERSION}." >&2
  exit 1
fi

if [[ "${source_akmods}" != "${stable_akmods}" ]]; then
  skopeo copy --retry-times 3 \
    --src-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
    --dest-creds "${REGISTRY_ACTOR}:${REGISTRY_TOKEN}" \
    "${source_akmods}" "${stable_akmods}"
else
  echo "Akmods source already at stable tag ${stable_akmods}; skipping retag copy."
fi

echo "Resolved candidate source ${candidate_image_by_tag} -> ${candidate_image}"
echo "Promoted ${candidate_image} -> ${stable_image}"
echo "Published audit tag ${audit_image}"
echo "Promoted ${source_akmods} -> ${stable_akmods}"
