#!/usr/bin/env bash
#
# Script: files/scripts/ensure-repo-signing-policy.sh
# What: Normalize image signature trust policy for both stable and candidate repos.
# Doing: Ensures both key filenames exist, then writes policy + registries config
#        entries for both repository names.
# Why: Main workflow builds a candidate-named image and then promotes by copying
#      tags; without this normalization, the promoted stable image can carry only
#      candidate-scoped trust config.
# Goal: Make signed host-side switches reliable in both directions:
#       stable <-> candidate.
#
set -euo pipefail

# Core paths used by containers/image policy and sigstore attachment discovery.
policy_file="/etc/containers/policy.json"
registries_dir="/etc/containers/registries.d"
key_dir="/etc/pki/containers"

# Repository names this project uses in GHCR.
stable_image_name="kinoite-zfs"
candidate_image_name="kinoite-zfs-candidate"

# Public key filenames expected by policy entries for each repo.
stable_key="${key_dir}/${stable_image_name}.pub"
candidate_key="${key_dir}/${candidate_image_name}.pub"

# Prefer deriving registry namespace from existing policy entries.
# Fall back to the current repository default if no matching entry exists.
repo_prefix="$(python3 - <<'PY'
import json
from pathlib import Path

policy = Path("/etc/containers/policy.json")
default = "ghcr.io/danathar"

if not policy.exists():
    print(default)
    raise SystemExit(0)

data = json.loads(policy.read_text(encoding="utf-8"))
docker = data.get("transports", {}).get("docker", {})
for repo in docker.keys():
    if repo.endswith("/kinoite-zfs-candidate"):
        print(repo.rsplit("/", 1)[0])
        raise SystemExit(0)
    if repo.endswith("/kinoite-zfs"):
        print(repo.rsplit("/", 1)[0])
        raise SystemExit(0)

print(default)
PY
)"

stable_repo="${repo_prefix}/${stable_image_name}"
candidate_repo="${repo_prefix}/${candidate_image_name}"
stable_registry_file="${registries_dir}/${stable_image_name}.yaml"
candidate_registry_file="${registries_dir}/${candidate_image_name}.yaml"

# Remove any pre-existing registry config files that already point at these
# repository names.
# Why: the BlueBuild `signing` module can create owner-prefixed filenames such as
# `danathar-kinoite-zfs-candidate.yaml` for the same namespace we normalize here.
# `containers/image` treats duplicate namespace definitions as a hard parse error,
# so leaving both files in place breaks `bootc switch`, `bootc upgrade`, and
# signed `rpm-ostree rebase` flows before signature verification even starts.
shopt -s nullglob
for registry_file in "${registries_dir}"/*.yaml "${registries_dir}"/*.yml; do
  case "${registry_file}" in
    "${stable_registry_file}" | "${candidate_registry_file}")
      # These are the canonical files we are about to overwrite below.
      continue
      ;;
  esac

  if grep -Fq "${stable_repo}:" "${registry_file}" || grep -Fq "${candidate_repo}:" "${registry_file}"; then
    rm -f "${registry_file}"
  fi
done
shopt -u nullglob

# Ensure both expected key filenames exist, regardless of whether we built
# candidate or stable naming for this image.
if [[ -f "${candidate_key}" && ! -f "${stable_key}" ]]; then
  cp -a "${candidate_key}" "${stable_key}"
fi
if [[ -f "${stable_key}" && ! -f "${candidate_key}" ]]; then
  cp -a "${stable_key}" "${candidate_key}"
fi

if [[ ! -f "${stable_key}" || ! -f "${candidate_key}" ]]; then
  echo "Missing signing public keys in ${key_dir}" >&2
  exit 1
fi

# Update policy.json so both repositories are accepted with sigstore signatures.
# We write directly as JSON (instead of string replacement) to keep output valid
# and deterministic.
STABLE_REPO="${stable_repo}" CANDIDATE_REPO="${candidate_repo}" python3 - <<'PY'
import json
import os
from pathlib import Path

policy_file = Path("/etc/containers/policy.json")
data = json.loads(policy_file.read_text(encoding="utf-8"))
stable_repo = os.environ["STABLE_REPO"]
candidate_repo = os.environ["CANDIDATE_REPO"]

data.setdefault("transports", {})
data["transports"].setdefault("docker", {})
docker = data["transports"]["docker"]

docker[stable_repo] = [
    {
        "type": "sigstoreSigned",
        "keyPath": "/etc/pki/containers/kinoite-zfs.pub",
        "signedIdentity": {"type": "matchRepository"},
    }
]

docker[candidate_repo] = [
    {
        "type": "sigstoreSigned",
        "keyPath": "/etc/pki/containers/kinoite-zfs-candidate.pub",
        "signedIdentity": {"type": "matchRepository"},
    }
]

policy_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

# Ensure sigstore OCI-attachment discovery is enabled for both repos.
# This is required for signature lookup in many host-side import paths.
cat > "${stable_registry_file}" <<EOF_REG_STABLE
docker:
  ${stable_repo}:
    use-sigstore-attachments: true
EOF_REG_STABLE

cat > "${candidate_registry_file}" <<EOF_REG_CANDIDATE
docker:
  ${candidate_repo}:
    use-sigstore-attachments: true
EOF_REG_CANDIDATE

# Keep file permissions consistent with the rest of container trust material.
chmod 0644 \
  "${stable_registry_file}" \
  "${candidate_registry_file}" \
  "${stable_key}" \
  "${candidate_key}"
