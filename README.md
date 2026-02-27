# Kinoite-ZFS

[![Build Main Image](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml/badge.svg)](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml)

This repository exists to test and validate ZFS support on Kinoite images built with BlueBuild.

Core goal:

- Track the current Kinoite/Fedora kernel stream.
- Build matching ZFS akmods against that kernel.
- Install those ZFS RPMs directly into the final image.
- Catch kernel/module mismatches during CI, before rebasing a host.

Quick terms used in this repo:

- `CI`: the GitHub Actions workflows in `.github/workflows`.
- `candidate`: test image/tag built first.
- `stable`: user-facing tags (`latest` and `main-<fedora>`).
- `workflow metadata`: run details like run ID, run number, branch/ref, commit SHA, and triggering user.
- `build-inputs` artifact: JSON file saved per run with the exact inputs that run used.
- `image ref`: text that points to a container image, usually `name:tag` (moving) or `name@sha256:digest` (exact).

If you want the full technical design and workflow details, read:

- `docs/architecture-overview.md` (high-level architecture: what/why/how)
- `docs/upstream-change-response.md` (user/operator failure response guide)
- `docs/akmods-fork-maintenance.md` (how to maintain and update the pinned akmods fork source)
- `docs/zfs-kinoite-testing.md`

That document is maintained as a living record and will be updated as each hardening issue is addressed.

## What Gets Published

- Candidate image (pre-promotion):
  - `ghcr.io/danathar/kinoite-zfs:candidate`
- Candidate akmods cache image (pre-promotion):
  - `ghcr.io/danathar/akmods-zfs-candidate:main-<fedora>`
- Stable image (promoted only after candidate success):
  - `ghcr.io/danathar/kinoite-zfs:latest`
- Stable image audit tag (immutable per promotion):
  - `ghcr.io/danathar/kinoite-zfs:stable-<run>-<sha>`
- Stable akmods cache image (promoted from candidate cache):
  - `ghcr.io/danathar/akmods-zfs:main-<fedora>`
- Branch test image:
  - `ghcr.io/danathar/kinoite-zfs:beta-<branch>`
- Branch akmods cache image:
  - `ghcr.io/danathar/akmods-zfs-<branch>:main-<fedora>`

Candidate and branch artifacts are isolated so test runs do not overwrite stable `latest` artifacts.

## Why Candidate First

This repo uses a two-step safety model:

1. Build/test candidate outputs first.
2. Promote to stable tags only if candidate succeeds.

If candidate fails, stable tags are not updated. That protects users from overnight upstream breakage and keeps stable on the last known-good build.

## Workflows

- `.github/workflows/build.yml`
  - Builds candidate artifacts first, then promotes them to stable tags on success.
  - Pins candidate compose to a resolved immutable base image tag per run to avoid mid-run `latest` drift.
  - Runs on `main` pushes, nightly schedule, and manual dispatch.
  - Uploads a `build-inputs-<run_id>` artifact capturing exact resolved build inputs.
- `.github/workflows/build-beta.yml`
  - Builds branch-tagged test artifacts for non-main branches.
  - Runs on branch pushes and manual dispatch.
- `.github/workflows/build-pr.yml`
  - PR validation build only (`push: false`, unsigned).

Markdown/docs-only changes do not trigger image builds.

## Reproducible Replay

Issue #3 mitigation adds lock-based replay support:

1. Each main workflow run publishes a `build-inputs-<run_id>` artifact.
2. To replay a known run, copy those values into `ci/inputs.lock.json`.
3. Manually run `Build And Promote Main Image` with:
   - `use_input_lock=true`
   - `build_container_image=<value from lock file>`
   - `promote_to_stable=false` (recommended for validation)

This allows you to rebuild with pinned base image/build container inputs instead of floating `latest` refs.

## Install And Rebase

> [!WARNING]
> This is an experimental image stream for testing.

Rebase in two steps so signing policies are available:

```bash
rpm-ostree rebase ostree-unverified-registry:ghcr.io/danathar/kinoite-zfs:latest
systemctl reboot
rpm-ostree rebase ostree-image-signed:docker://ghcr.io/danathar/kinoite-zfs:latest
systemctl reboot
```

## Quick Validation

After reboot:

```bash
rpm -q kmod-zfs
modinfo zfs | head
zpool --version
zfs --version
```

For VM testing with a secondary disk (example `/dev/vdb`):

```bash
sudo wipefs -a /dev/vdb
sudo zpool create -f -o ashift=12 -O mountpoint=none testpool /dev/vdb
sudo zfs create -o mountpoint=/var/mnt/testpool testpool/data
sudo zpool status
sudo zfs list
```

## Signature Verification

```bash
cosign verify --key cosign.pub ghcr.io/danathar/kinoite-zfs
```

## References

- BlueBuild setup docs: https://blue-build.org/how-to/setup/
- Fedora ostree native containers: https://www.fedoraproject.org/wiki/Changes/OstreeNativeContainerStable
