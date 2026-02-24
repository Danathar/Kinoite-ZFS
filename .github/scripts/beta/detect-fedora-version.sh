#!/usr/bin/env bash
set -euo pipefail

# Read kernel release label from current Kinoite main stream.
# This keeps branch akmods/image builds aligned with current base kernel stream.
ostree_linux="$(skopeo inspect docker://ghcr.io/ublue-os/kinoite-main:latest --format '{{ index .Labels "ostree.linux" }}')"
# Derive Fedora major (e.g., 43) from kernel release suffix (...fc43...).
fedora_version="$(sed -E 's/.*fc([0-9]+).*/\1/' <<< "${ostree_linux}")"

# Fail early if parsing breaks, so downstream jobs don't use invalid tags.
if [[ -z "${fedora_version}" ]]; then
  echo "Failed to detect Fedora version from ostree.linux=${ostree_linux}" >&2
  exit 1
fi

# Publish outputs consumed by cache checks and akmods build configuration.
{
  echo "version=${fedora_version}"
  echo "kernel_release=${ostree_linux}"
} >> "${GITHUB_OUTPUT}"
