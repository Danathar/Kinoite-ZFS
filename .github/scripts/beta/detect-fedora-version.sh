#!/usr/bin/env bash
set -euo pipefail

ostree_linux="$(skopeo inspect docker://ghcr.io/ublue-os/kinoite-main:latest --format '{{ index .Labels "ostree.linux" }}')"
fedora_version="$(sed -E 's/.*fc([0-9]+).*/\1/' <<< "${ostree_linux}")"

if [[ -z "${fedora_version}" ]]; then
  echo "Failed to detect Fedora version from ostree.linux=${ostree_linux}" >&2
  exit 1
fi

{
  echo "version=${fedora_version}"
  echo "kernel_release=${ostree_linux}"
} >> "${GITHUB_OUTPUT}"
