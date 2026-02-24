#!/usr/bin/env bash
# Script: beta/configure-branch-recipe.sh
# What: Rewrites recipe and ZFS containerfile references for branch builds.
# Doing: Sets branch image tag in `recipes/recipe.yml` and branch akmods source in `containerfiles/zfs-akmods/Containerfile`.
# Why: Ensures branch runs do not overwrite main tags/caches while still using the same build logic.
# Goal: Point branch image build at branch-scoped outputs with full traceability in logs.
set -euo pipefail

# Normalize owner name for OCI repository path usage.
IMAGE_ORG="$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')"
# ZFS install logic now lives in an external containerfile snippet.
ZFS_CONTAINERFILE="containerfiles/zfs-akmods/Containerfile"

# Branch builds publish to a branch tag to avoid overwriting main's `latest`.
sed -i -E "s/^image-version:.*/image-version: ${IMAGE_TAG}/" recipes/recipe.yml
# Point the containerfile logic at this branch's isolated akmods cache repo.
sed -i -E "s#^AKMODS_IMAGE=.*#AKMODS_IMAGE=\"ghcr.io/${IMAGE_ORG}/${AKMODS_REPO}:main-\\\${FEDORA_VERSION}\"#" "${ZFS_CONTAINERFILE}"

# Emit effective values for audit/debug visibility in logs.
grep -n '^image-version:' recipes/recipe.yml
grep -n '^AKMODS_IMAGE=' "${ZFS_CONTAINERFILE}"
