#!/usr/bin/env bash
set -euo pipefail

IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"

sed -i -E "s/^image-version:.*/image-version: ${IMAGE_TAG}/" recipes/recipe.yml
sed -i -E "s#^base-image:.*#base-image: ${BASE_IMAGE_PINNED}#" recipes/recipe.yml
sed -i -E "s#^[[:space:]]*AKMODS_IMAGE=.*#        AKMODS_IMAGE=\"ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-\\\${FEDORA_VERSION}\"#" recipes/recipe.yml

grep -n '^base-image:' recipes/recipe.yml
grep -n '^image-version:' recipes/recipe.yml
grep -n 'AKMODS_IMAGE=' recipes/recipe.yml
