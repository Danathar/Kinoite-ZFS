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
   - Main pipeline: builds candidate artifacts first and promotes to stable only after candidate success.
3. `.github/workflows/build-beta.yml`
   - Branch pipeline: builds/publishes branch-isolated akmods and branch-tagged OS image.
4. `.github/workflows/build-pr.yml`
   - Pull request validation build with no push/signing.
5. `ci/inputs.lock.json`
   - Optional pinned input file used by replay mode for deterministic rebuilds.

## Artifact Strategy

### Main Artifacts

1. Candidate OS image: `ghcr.io/danathar/kinoite-zfs:candidate`
2. Candidate akmods cache image: `ghcr.io/danathar/akmods-zfs-candidate:main-<fedora>`
3. Stable OS image: `ghcr.io/danathar/kinoite-zfs:latest`
4. Stable OS audit tag: `ghcr.io/danathar/kinoite-zfs:stable-<run>-<sha>`
5. Stable akmods cache image: `ghcr.io/danathar/akmods-zfs:main-<fedora>`

### Branch Artifacts

1. OS image: `ghcr.io/danathar/kinoite-zfs:beta-<branch>`
2. Akmods cache image: `ghcr.io/danathar/akmods-zfs-<branch>:main-<fedora>`

Branch artifacts are isolated by both tag and repo name to avoid clobbering main caches.

## End-To-End Build Flow

### 1. Detect Base Kernel Stream

The main workflow resolves build inputs in one of two modes:

1. Default mode: resolve floating refs (for example `kinoite-main:latest`) to immutable digests at run time.
2. Replay mode: read pinned inputs from `ci/inputs.lock.json` when `use_input_lock=true`.

After resolving the base image ref, it reads `ostree.linux` to obtain:

1. The full kernel release (example: `6.18.12-200.fc43.x86_64`).
2. Fedora major version (example: `43`).

This ensures akmods cache and final image build both align to the same kernel stream.

The workflow also writes a `build-inputs-<run_id>` artifact containing all resolved inputs (base image digest, builder digest, kernel, ZFS line, and akmods ref) for audit and replay.

### 2. Validate Existing Candidate Akmods Cache

Before rebuilding akmods, CI checks whether the existing candidate cache image already contains:

1. `kmod-zfs-<exact-kernel-release>-*.rpm` for the current base kernel.

If a matching RPM exists, akmods rebuild is skipped.
If missing, akmods rebuild is forced.

This is the core mechanism that prevents shipping stale kmods.

### 3. Build Candidate Akmods (When Required)

If cache is missing/stale (or manual rebuild is requested), CI:

1. Fetches a pinned upstream `ublue-os/akmods` commit.
2. Injects the ZFS image target under this repo owner namespace.
3. Applies controlled runtime patches needed by current ZFS build flow.
4. Builds and publishes candidate akmods cache image.

### 4. Build Candidate Kinoite Image

`recipes/recipe.yml` is rewritten in-run to point at candidate tags, then:

1. Pulls the akmods cache image.
2. Extracts ZFS RPMs from image layers.
3. Installs RPMs via `rpm-ostree install`.
4. Verifies `/lib/modules/<kernel>/extra/zfs/zfs.ko` exists for each base kernel.
5. Runs `depmod -a <kernel>` to ensure module dependency metadata is generated in build context.

If module files do not match kernel directories, candidate build fails immediately.

### 5. Promote Candidate To Stable

Promotion runs only after successful candidate akmods and candidate image jobs:

1. Retags candidate image to stable `latest`.
2. Publishes immutable stable audit tag (`stable-<run>-<sha>`).
3. Retags candidate akmods cache to stable akmods tag.

If candidate fails, promotion does not run, and the previous stable tags remain unchanged.

## Workflow Behavior

### `.github/workflows/build.yml` (Main)

Triggers:

1. Push to `main`.
2. Nightly schedule.
3. Manual dispatch.

Key behavior:

1. Builds/publishes candidate akmods cache as needed.
2. Builds/publishes candidate image.
3. Promotes candidate artifacts to stable tags only on success.
4. Manual dispatch supports candidate-only runs by setting `promote_to_stable=false`.
5. Manual dispatch supports lock replay (`use_input_lock=true`) with pinned refs from `ci/inputs.lock.json`.
6. Uploads a per-run build input manifest artifact (`build-inputs-<run_id>`).
7. Ignores markdown/docs-only changes.

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
Candidate-first promotion adds one more safeguard: if candidate fails, stable tags are not advanced.

Important limitation:

1. Previously published tags remain available.
2. A failing candidate run does not retroactively remove old stable tags.
3. Stable remains at last successful promotion until compatibility returns.
4. Consumers should rebase intentionally and validate after kernel transitions.

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

## Issue #2: No Compatibility Holdback When Fedora Kernel Jumps Ahead

Problem:

1. Main builds intentionally track `kinoite-main:latest` and therefore track new Fedora kernels quickly.
2. When Fedora publishes a kernel before OpenZFS/akmods is compatible, builds can fail until upstream support catches up.
3. There is currently no explicit holdback/freeze mechanism in this repo to keep publishing a known-good compatible stream during that window.

Mitigation implemented:

1. Implemented candidate-first pipeline in `.github/workflows/build.yml`.
2. Main workflow now publishes candidate artifacts (`candidate` image + `akmods-zfs-candidate`) before touching stable tags.
3. Added gated promotion job that retags candidate artifacts to stable only when candidate jobs succeed.
4. Added manual dispatch input `promote_to_stable` for controlled candidate-only runs.

Where:

1. `.github/workflows/build.yml`

Residual risk:

1. Stable can intentionally lag behind upstream latest during compatibility gaps.
2. Promotion still assumes candidate build success is sufficient quality signal (no booted runtime smoke test yet).

Planned follow-up:

1. Add runtime smoke testing before promotion so candidate success is validated in a booted environment.
2. Define policy for communicating stable lag windows when candidate repeatedly fails.

## Issue #3: Build Inputs Are Still Partially Floating (Limited Reproducibility)

Problem:

1. The pipeline intentionally consumes moving sources such as `kinoite-main:latest` and `devcontainer:latest`.
2. `ZFS_MINOR_VERSION` is pinned only at minor line (`2.4`), not a fully fixed patch release.
3. Two runs at different times can differ even with the same repository commit, which complicates debugging and forensic rollback.

Mitigation implemented:

1. Added lock replay inputs to `.github/workflows/build.yml` (`use_input_lock`, `lock_file`, `build_container_image`).
2. Added deterministic input resolution step that records immutable digests for base image and builder container.
3. Candidate image recipe now rewrites `base-image:` to digest-pinned base reference for per-run determinism.
4. Added build input manifest artifact upload (`build-inputs-<run_id>`) for audit and reproducible reruns.
5. Added repository lock file `ci/inputs.lock.json` for replay mode.

Where:

1. `.github/workflows/build.yml`
2. `ci/inputs.lock.json`

Residual risk:

1. Default scheduled/push runs still follow moving upstream inputs by design (to catch breakage early).
2. Replay mode requires operator discipline to keep `ci/inputs.lock.json` aligned with a selected run artifact.
3. ZFS version is still pinned at minor line unless replay lock sets a different value.

Planned follow-up:

1. Add OCI labels with resolved input metadata to published candidate/stable images.
2. Add a helper script to auto-sync `ci/inputs.lock.json` from a selected run artifact.

## Issue #4: Runtime Patching Is Operationally Fragile

Problem:

1. The workflow currently patches upstream build scripts at runtime (`jq` and `python3-cffi` injection).
2. Issue #1 added guardrails so patch drift fails fast, but the approach still depends on maintaining downstream patch logic.
3. Each upstream packaging change can require local patch updates before builds resume.

Mitigation implemented:

1. Pending beyond Issue #1 guardrails.

Residual risk:

1. Maintenance burden remains on this repo.
2. Future upstream changes can still break builds until local patches are updated.

Planned follow-up:

1. Reduce local patch surface by upstreaming required changes or using a maintained fork/input with those fixes.
2. Reassess and remove runtime patches where no longer required.

## Issue #5: No Automated Runtime Smoke Test Of ZFS In A Booted Image

Problem:

1. Current CI verifies module artifacts exist and runs `depmod`, but does not boot the produced image and execute runtime checks.
2. A build can succeed while runtime behavior still fails in edge cases (for example, module load behavior after boot on target kernel/userspace).

Mitigation implemented:

1. Pending.

Residual risk:

1. Some failures are discovered only after manual VM rebase/testing.
2. Validation latency is higher during kernel or OpenZFS transitions.

Planned follow-up:

1. Add automated post-build smoke tests against a booted test VM/image.
2. Include `modprobe zfs`, `zpool`, and dataset creation checks in that smoke path.

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
