# ZFS On Kinoite Testing Design

## Purpose

This repository is a controlled testbed for ZFS support on Kinoite-based images built with BlueBuild.

The objective is to validate that we can safely:

1. Track the current Kinoite/Fedora kernel stream.
2. Build ZFS kernel modules (`kmod-zfs`) against that exact kernel stream.
3. Install those modules into the final ostree image.
4. Fail in CI when kernel/module compatibility breaks, instead of discovering it after rebasing a desktop or host.

This is intentionally designed for iterative validation before adopting any approach on production-like systems.

## Constraints And Context

1. Kinoite uses immutable/ostree workflows, so custom kernel module integration must happen during image build.
2. ZFS kernel module compatibility can lag behind new Fedora kernel releases.
3. Branch testing must never overwrite production (`main`) image tags or akmods caches.
4. CI must detect stale ZFS module caches and rebuild when needed.

## Repository Components

1. `recipes/recipe.yml`
   - Defines the final image (`kinoite-zfs`) and installs ZFS RPMs from a self-hosted akmods image.
2. `.github/workflows/build.yml`
   - Main pipeline: builds/publishes main akmods and main OS image.
3. `.github/workflows/build-beta.yml`
   - Branch pipeline: builds/publishes branch-isolated akmods and branch-tagged OS image.
4. `.github/workflows/build-pr.yml`
   - Pull request validation build with no push/signing.

## Artifact Strategy

### Main Artifacts

1. OS image: `ghcr.io/danathar/kinoite-zfs:latest`
2. Akmods cache image: `ghcr.io/danathar/akmods-zfs:main-<fedora>`

### Branch Artifacts

1. OS image: `ghcr.io/danathar/kinoite-zfs:beta-<branch>`
2. Akmods cache image: `ghcr.io/danathar/akmods-zfs-<branch>:main-<fedora>`

Branch artifacts are isolated by both tag and repo name to avoid clobbering main caches.

## End-To-End Build Flow

### 1. Detect Base Kernel Stream

The workflows inspect `ghcr.io/ublue-os/kinoite-main:latest` and read `ostree.linux` to obtain:

1. The full kernel release (example: `6.18.12-200.fc43.x86_64`).
2. Fedora major version (example: `43`).

This ensures akmods cache and final image build both align to the same kernel stream.

### 2. Validate Existing Akmods Cache

Before rebuilding akmods, CI checks whether the existing cache image already contains:

1. `kmod-zfs-<exact-kernel-release>-*.rpm` for the current base kernel.

If a matching RPM exists, akmods rebuild is skipped.
If missing, akmods rebuild is forced.

This is the core mechanism that prevents shipping stale kmods.

### 3. Build Akmods (When Required)

If cache is missing/stale (or manual rebuild is requested), CI:

1. Fetches a pinned upstream `ublue-os/akmods` commit.
2. Injects the ZFS image target under this repo owner namespace.
3. Applies controlled runtime patches needed by current ZFS build flow.
4. Builds and publishes akmods cache image.

### 4. Build Final Kinoite Image

`recipes/recipe.yml` then:

1. Pulls the akmods cache image.
2. Extracts ZFS RPMs from image layers.
3. Installs RPMs via `rpm-ostree install`.
4. Verifies `/lib/modules/<kernel>/extra/zfs/zfs.ko` exists for each base kernel.
5. Runs `depmod -a <kernel>` to ensure module dependency metadata is generated in build context.

If module files do not match kernel directories, build fails immediately.

## Workflow Behavior

### `.github/workflows/build.yml` (Main)

Triggers:

1. Push to `main`.
2. Nightly schedule.
3. Manual dispatch.

Key behavior:

1. Builds/publishes main akmods cache as needed.
2. Builds/publishes main image.
3. Ignores markdown/docs-only changes.

### `.github/workflows/build-beta.yml` (Branch)

Triggers:

1. Push to non-main branches.
2. Manual dispatch.

Key behavior:

1. Computes branch-safe image tag and branch-specific akmods repo name.
2. Builds/publishes branch-isolated akmods cache as needed.
3. Rewrites `recipes/recipe.yml` in-run to consume branch-scoped akmods source.
4. Builds/publishes branch-tagged image.
5. Ignores markdown/docs-only changes.

### `.github/workflows/build-pr.yml` (PR Validation)

Triggers:

1. Pull request updates.

Key behavior:

1. Build only; no push.
2. No signing requirement.
3. Ignores markdown/docs-only changes.

## Kernel Compatibility Risk Handling

When Fedora kernel updates faster than OpenZFS support:

1. Akmods build can fail at build stage.
2. Or cache validation can fail to find matching kernel RPM.
3. Or final image validation can fail because `zfs.ko` is absent for base kernel.

In all cases, CI fails before publishing a broken final image for that run.

Important limitation:

1. Previously published tags remain available.
2. A newly failing run does not retroactively remove old tags.
3. Consumers should rebase intentionally and validate after kernel transitions.

## Living Issue Log

This section is updated for each tracked issue as we work through hardening items.
For each new issue, add a section with:

1. Problem
2. Mitigation implemented
3. Residual risk
4. Planned follow-up

## Issue #1: Upstream Source Drift In Akmods Tooling

Problem:

1. Building from floating `ublue-os/akmods` `main` can break unexpectedly if upstream scripts change.
2. Runtime patches can silently stop applying if anchor lines move.

Mitigation implemented:

1. Pin upstream akmods source to explicit commit:
   - `906e565f712f43a598dcd272dc8ca053fcc99116`
2. Fetch exactly that commit and verify resolved SHA matches expected.
3. Add fail-fast guard checks before and after runtime patch injection:
   - Verify patch anchor lines exist.
   - Verify injected lines actually appear.

Where:

1. `.github/workflows/build.yml`
2. `.github/workflows/build-beta.yml`

Residual risk:

1. Pinned commit can become outdated for future Fedora/ZFS changes.
2. Manual pin updates are required when intentionally moving to newer upstream akmods logic.

Planned follow-up:

1. Add update cadence/process for bumping pinned akmods ref after validation.

## Issue #2: Placeholder (Title Pending)

Problem:

1. Pending definition from prior review notes.

Mitigation implemented:

1. Pending.

Residual risk:

1. Pending.

Planned follow-up:

1. Define exact mitigation and validate on branch image before promoting.

## Issue #3: Placeholder (Title Pending)

Problem:

1. Pending definition from prior review notes.

Mitigation implemented:

1. Pending.

Residual risk:

1. Pending.

Planned follow-up:

1. Define exact mitigation and validate on branch image before promoting.

## Issue #4: Placeholder (Title Pending)

Problem:

1. Pending definition from prior review notes.

Mitigation implemented:

1. Pending.

Residual risk:

1. Pending.

Planned follow-up:

1. Define exact mitigation and validate on branch image before promoting.

## Issue #5: Placeholder (Title Pending)

Problem:

1. Pending definition from prior review notes.

Mitigation implemented:

1. Pending.

Residual risk:

1. Pending.

Planned follow-up:

1. Define exact mitigation and validate on branch image before promoting.

## How To Test In A VM

Assume VM has a secondary blank disk at `/dev/vdb`.

1. Rebase to test image.
2. Reboot.
3. Validate package/module visibility.
4. Create a non-root-mounted test dataset.

Commands:

```bash
rpm -q kmod-zfs
sudo modprobe zfs
zpool --version
zfs --version

sudo wipefs -a /dev/vdb
sudo zpool create -f -o ashift=12 -O mountpoint=none testpool /dev/vdb
sudo zfs create -o mountpoint=/var/mnt/testpool testpool/data
sudo zpool status
sudo zfs list
```

Note:

1. Atomic root is read-only; avoid mounting test datasets directly under `/`.
2. Use `/var/...` mountpoints for host-mounted datasets.

## Troubleshooting

### `modprobe: FATAL: Module zfs not found in directory /lib/modules/<kernel>`

Likely causes:

1. Installed `kmod-zfs` does not match current kernel.
2. Cache image contained stale kernel RPMs.

Checks:

```bash
uname -r
rpm -qa | grep -E '^kmod-zfs|^zfs'
find /lib/modules/$(uname -r) -maxdepth 4 -type f -name 'zfs.ko*'
```

### `cannot mount '/testpool': failed to create mountpoint: Read-only file system`

Cause:

1. ZFS default mountpoint attempted under `/` on an immutable host.

Fix:

```bash
sudo zpool create -f -o ashift=12 -O mountpoint=none testpool /dev/vdb
sudo zfs create -o mountpoint=/var/mnt/testpool testpool/data
```

### `/dev/vdb is in use and contains an unknown filesystem`

Cause:

1. Prior ZFS labels or other signatures remain on the test disk.

Fix:

```bash
sudo zpool destroy -f testpool 2>/dev/null || true
sudo wipefs -a /dev/vdb
```

## Maintenance Guidance

1. Keep `ZFS_MINOR_VERSION` explicit in workflows and update intentionally.
2. Treat the pinned akmods commit as a controlled dependency.
3. Test new compatibility changes on branch workflow first.
4. Promote to `main` only after VM validation passes.
5. Update this document whenever a new issue is worked and resolved.
