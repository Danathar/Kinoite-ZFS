#!/usr/bin/env bash
# Script: akmods/build-and-publish.sh
# What: Executes the upstream akmods build/publish lifecycle from a prepared /tmp/akmods checkout.
# Doing: Runs `just build`, `just login`, `just push`, and `just manifest` in order.
# Why: Centralizes akmods publish behavior so workflows stay orchestration-focused and deterministic.
# Goal: Produce and publish the ZFS akmods cache image/manifest for the current pipeline context.
set -euo pipefail

# Upstream akmods tooling expects to run from its repository root in /tmp/akmods.
cd /tmp/akmods

# Optional hardening: pin upstream akmods build to the exact kernel release resolved
# from the base image inputs. This avoids kernel drift between jobs.
if [[ -n "${KERNEL_RELEASE:-}" ]]; then
  if [[ -z "${AKMODS_KERNEL:-}" || -z "${AKMODS_VERSION:-}" ]]; then
    echo "AKMODS_KERNEL and AKMODS_VERSION are required when KERNEL_RELEASE is set" >&2
    exit 1
  fi

  kernel_flavor="${AKMODS_KERNEL}"
  build_id="${kernel_flavor}-${AKMODS_VERSION}"
  build_root="${AKMODS_BUILDDIR:-$(pwd)/build}"
  version_cache="${build_root}/${build_id}"
  kcwd="${version_cache}/KCWD"
  kcpath="${KCPATH:-${kcwd}/rpms}"
  version_json="${kcpath}/cache.json"
  kernel_major_minor_patch="$(cut -d '.' -f1-3 <<< "${KERNEL_RELEASE}")"
  kernel_name="kernel"

  if [[ "${kernel_flavor}" == longterm* ]]; then
    kernel_name="kernel-longterm"
  fi

  mkdir -p "${kcpath}"
  jq -n \
    --arg build_tag "" \
    --arg kernel_flavor "${kernel_flavor}" \
    --arg kernel_major_minor_patch "${kernel_major_minor_patch}" \
    --arg kernel_release "${KERNEL_RELEASE}" \
    --arg kernel_name "${kernel_name}" \
    --arg KCWD "${kcwd}" \
    --arg KCPATH "${kcpath}" \
    '{
      "kernel_build_tag": $build_tag,
      "kernel_flavor": $kernel_flavor,
      "kernel_major_minor_patch": $kernel_major_minor_patch,
      "kernel_release": $kernel_release,
      "kernel_name": $kernel_name,
      "KCWD": $KCWD,
      "KCPATH": $KCPATH
    }' > "${version_json}"

  echo "Pinned akmods kernel release to ${KERNEL_RELEASE}"
  echo "Seeded ${version_json}"
fi

# Build target RPMs/images for the configured akmods target (zfs in our workflows).
just build
# Authenticate to GHCR using credentials exported by the workflow step env.
just login
# Push per-arch image layers for the configured akmods cache repository/tag.
just push
# Publish/update the multi-arch manifest list after pushing image layers.
just manifest
