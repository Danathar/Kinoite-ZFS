#!/usr/bin/env bash
#
# Script: scripts/fix-host-signing-policy.sh
# What: Repairs host-side trust config for this repo's stable and candidate images.
# Doing: Installs the public key under both expected filenames, then reuses the
#        same normalization script shipped in the image build to rewrite policy
#        and sigstore attachment discovery files.
# Why: Older already-booted repo images can carry missing or duplicate trust
#      entries, which makes `bootc switch` / `bootc upgrade` fail before image
#      import completes.
# Goal: Restore a host to the expected trust layout so signed updates work again.
#
set -euo pipefail

# Resolve repository root relative to this script so the command works from any
# current directory while you are inside a checked-out copy of this repo.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
public_key="${repo_root}/cosign.pub"
normalizer="${repo_root}/files/scripts/ensure-repo-signing-policy.sh"

if [[ ! -f "${public_key}" ]]; then
  echo "Missing public key file: ${public_key}" >&2
  exit 1
fi
if [[ ! -f "${normalizer}" ]]; then
  echo "Missing policy normalization script: ${normalizer}" >&2
  exit 1
fi

# Place the same public key under both repo-specific filenames because policy
# entries refer to stable and candidate repos separately.
install -d -m 0755 /etc/pki/containers /etc/containers/registries.d
install -m 0644 "${public_key}" /etc/pki/containers/kinoite-zfs.pub
install -m 0644 "${public_key}" /etc/pki/containers/kinoite-zfs-candidate.pub

# Reuse the in-image normalizer so host repair and image build stay aligned.
bash "${normalizer}"

cat <<'EOF'
Host signing policy repaired.

Next step:
  sudo bootc switch ghcr.io/danathar/kinoite-zfs:latest

If you are already tracking that ref, `sudo bootc upgrade` is also valid.
EOF
