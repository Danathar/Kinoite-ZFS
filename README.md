# Kinoite-ZFS

[![Build Main Image](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml/badge.svg)](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml)

This repository exists to test and validate ZFS support on Kinoite images built with BlueBuild.

If you are new to ZFS:

- ZFS is a filesystem + volume manager focused on data integrity and storage management features (for example checksums, snapshots, and pooled storage).
- In this repo, the key detail is that ZFS needs kernel modules that must match the running kernel version.
- Owner opinion around here: ZFS is awesome and everyone should use it :)

Core goal:

- Track the current Kinoite/Fedora kernel stream.
- Build matching ZFS akmods against that kernel.
- Install those ZFS RPMs directly into the final image.
- Catch kernel/module mismatches during CI, before rebasing a host.
- Keep the workflow reusable as a template so users can adapt it to other Universal Blue or Fedora Atomic images if they want ZFS support there.

## If You Are New To Akmods And Atomic Images

`akmod` (automatic kernel module) packages are a way to provide out-of-tree
kernel modules, like ZFS, for a specific kernel release.

Why this matters here:

1. Kinoite/Aurora-style systems are image-based and mostly immutable.
2. You usually do not want ad-hoc module build steps happening directly on every client machine.
3. Instead, we build and validate matching ZFS kernel modules in our pipeline (the ordered set of build/check/publish steps in one workflow run), then bake those RPMs into the final image.

In plain terms, this project is doing:

1. Read current upstream kernel version from labels stored in Kinoite base image metadata (extra descriptive data attached to the image).
2. Build (or reuse) ZFS akmods that exactly match that kernel.
3. Build a candidate custom image (`candidate` = test image built first) that installs those ZFS RPMs.
4. Promote to stable tags (`stable` = normal user-facing tags) only if candidate build/test checks succeed.

So the safety model is: test first, then promote.
If something upstream changes and breaks compatibility, candidate fails and stable does not move.

## Current Ecosystem Issue (Aurora/Kinoite/Silverblue Context)

The core issue is not "immutability is broken." The main issue is version timing:

1. Fedora-family systems move kernels forward quickly.
2. ZFS is an out-of-tree kernel module, so it needs upstream OpenZFS support for each new kernel series.
3. There can be a time gap between "new kernel shipped" and "matching ZFS support/release available."
4. During that gap, image projects must choose between:
   - holding back kernels,
   - delaying ZFS-enabled image updates,
   - or removing/relaxing ZFS support.

What this repo does to handle that gap:

1. Resolve exact base-image/kernel inputs for each run.
2. Check whether cached ZFS modules match that exact kernel release.
3. Rebuild modules when they do not match.
4. Build candidate images first and only promote to stable when candidate succeeds.

This pipeline (ordered jobs/steps in one workflow run) does not eliminate upstream timing gaps, but it prevents silently shipping mismatched kernel/module combinations in this image stream.

As of February 27, 2026:

1. There are active discussions about possible future ZFS scope changes in some Universal Blue images (for example Aurora issue [#1765](https://github.com/ublue-os/aurora/issues/1765)).
2. The linked issue is currently open and framed as consideration/planning discussion, not a finalized global removal action.
3. A practical goal of this repository is continuity: if upstream image defaults change, this workflow can still be used as a starting template for self-maintained ZFS-enabled images.

Quick terms used in this repo:

- `CI`: the GitHub Actions workflows in `.github/workflows`.
- `candidate`: test image/tag built first.
- `stable`: user-facing tags (`latest` and `main-<fedora>`).
- `metadata`: descriptive data attached to an object (for example image labels or workflow run details).
- `workflow metadata`: run details like run ID, run number, branch/ref, commit SHA, and triggering user.
- `workflow run`: one execution of a GitHub Actions workflow from start to finish (one run has its own run ID and logs).
- `pipeline`: the ordered set of jobs/steps in a workflow run (for example: resolve inputs -> build candidate -> promote stable).
- `build-inputs` artifact: JSON file saved per run with the exact inputs that run used.
- `tag`: a human-readable label on an image, like `latest` or `main-43`.
- `image ref`: text that points to a container image, usually `name:tag` or `name@sha256:digest`.
- `floating ref` / `floating latest ref`: a tag-based ref (for example `:latest`) that can point to a different image later without changing its text.
- `digest-pinned ref`: an exact image pointer like `name@sha256:...`; this does not move to a different image unless you change the digest value.
- `tag vs digest-pinned` (plain language): a tag is a moving signpost, while a digest is an exact snapshot.

Common commands used in docs:

- `gh`: GitHub CLI. Used to list runs, inspect jobs, and download run files.
- `skopeo`: reads/copies container images without running them.
- `jq`: reads and filters JSON output.
- `rpm-ostree`: manages package layering/rebase on atomic Fedora systems (like Kinoite).
- `cosign`: verifies container image signatures.

If you want the full technical design and workflow details, read:

- [`docs/architecture-overview.md`](docs/architecture-overview.md) (high-level architecture: what/why/how)
- [`docs/upstream-change-response.md`](docs/upstream-change-response.md) (user/operator failure response guide)
- [`docs/akmods-fork-maintenance.md`](docs/akmods-fork-maintenance.md) (how to maintain and update the pinned akmods fork source)
- [`docs/zfs-kinoite-testing.md`](docs/zfs-kinoite-testing.md)

[`docs/zfs-kinoite-testing.md`](docs/zfs-kinoite-testing.md) is maintained as a living record and is updated as each hardening issue is addressed.

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

- [`.github/workflows/build.yml`](.github/workflows/build.yml)
  - Builds candidate artifacts first, then promotes them to stable tags on success.
  - Pins candidate compose to a resolved immutable base image tag per run to avoid mid-run `latest` drift.
  - Calls Python workflow helpers in `ci_tools/` directly through `python3 -m ci_tools.cli <command>`.
  - Runs on `main` pushes, nightly schedule, and manual dispatch.
  - Uploads a `build-inputs-<run_id>` artifact capturing exact resolved build inputs.
- [`.github/workflows/build-beta.yml`](.github/workflows/build-beta.yml)
  - Builds branch-tagged test artifacts for non-main branches.
  - Runs on branch pushes and manual dispatch.
- [`.github/workflows/build-pr.yml`](.github/workflows/build-pr.yml)
  - PR validation build only (`push: false`, unsigned).

Markdown/docs-only changes do not trigger image builds.

## Reproducible Replay

Lock-based replay support is available:

1. Each main workflow run publishes a `build-inputs-<run_id>` artifact.
2. To replay a known run, copy those values into [`ci/inputs.lock.json`](ci/inputs.lock.json).
3. Manually run `Build And Promote Main Image` with:
   - `use_input_lock=true`
   - `build_container_image=<value from lock file>`
   - `promote_to_stable=false` (recommended for validation)

This allows you to rebuild with pinned base image/build container inputs instead of floating `latest` refs (moving tags).

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
