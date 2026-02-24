#!/usr/bin/env bash
set -euo pipefail

IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
ZFS_CONTAINERFILE="containerfiles/zfs-akmods/Containerfile"

sed -i -E "s/^image-version:.*/image-version: ${IMAGE_TAG}/" recipes/recipe.yml
sed -i -E "s#^base-image:.*#base-image: ${BASE_IMAGE_PINNED}#" recipes/recipe.yml
sed -i -E "s#^AKMODS_IMAGE=.*#AKMODS_IMAGE=\"ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-\\\${FEDORA_VERSION}\"#" "${ZFS_CONTAINERFILE}"

grep -n '^base-image:' recipes/recipe.yml
grep -n '^image-version:' recipes/recipe.yml
grep -n '^AKMODS_IMAGE=' "${ZFS_CONTAINERFILE}"
