# ZFS On Kinoite Testing Design

## Purpose

This repository is a controlled testbed for ZFS support on Kinoite-based images built with BlueBuild.

The objective is to validate that we can safely:

1. Track the current Kinoite/Fedora kernel stream.
2. Build ZFS kernel modules (`kmod-zfs`) against that exact kernel stream (that exact point in the moving release flow).
3. Install those modules into the final ostree image.
4. Fail in CI when kernel/module compatibility breaks, instead of discovering it after rebasing a desktop or host.

This is intentionally designed for iterative validation before adopting any approach on production-like systems.

## Terminology

1. CI: the GitHub Actions workflows in this repo.
2. Candidate: a test build/tag created before stable tags are updated.
3. Stable: the tags users normally consume (`latest` and `main-<fedora>`).
4. Build inputs artifact: JSON file saved per run that records exact inputs.
5. Replay/lock mode: manual run mode that uses saved inputs from [`ci/inputs.lock.json`](../ci/inputs.lock.json).
6. Fedora/kernel stream: the moving sequence of new kernel releases over time.

## Command Notes

1. `gh`: GitHub CLI for workflow runs/logs/artifacts.
2. `skopeo`: inspect/copy container images directly.
3. `jq`: parse JSON output from CLI commands.
4. `rpm-ostree`: package/rebase management on atomic Fedora systems. Rebase means switching the installed OS image source ref.
5. `depmod`: rebuild kernel module dependency metadata for a target kernel.

## Constraints And Context

1. Kinoite uses immutable/ostree workflows, so custom kernel module integration must happen during image build.
2. ZFS kernel module compatibility can lag behind new Fedora kernel releases.
3. Branch testing must never overwrite production (`main`) image tags or akmods caches.
4. CI must detect stale ZFS module caches and rebuild when needed.

## Repository Components

1. [`recipes/recipe.yml`](../recipes/recipe.yml)
   - Defines the final image (`kinoite-zfs`) and installs ZFS RPMs from a self-hosted akmods image.
2. [`.github/workflows/build.yml`](../.github/workflows/build.yml)
   - Main pipeline: builds candidate artifacts first and promotes to stable only after candidate success.
3. [`.github/workflows/build-beta.yml`](../.github/workflows/build-beta.yml)
   - Branch pipeline: builds/publishes branch-isolated akmods and branch-tagged OS image.
4. [`.github/workflows/build-pr.yml`](../.github/workflows/build-pr.yml)
   - Pull request validation build with no push/signing.
5. [`ci/inputs.lock.json`](../ci/inputs.lock.json)
   - Optional pinned input file used by replay mode for deterministic rebuilds.

## Artifact Strategy

### Main Artifacts

1. Candidate source image tag: `ghcr.io/danathar/kinoite-zfs-candidate:<shortsha>-<fedora>`
2. Candidate akmods source tag: `ghcr.io/danathar/akmods-zfs-candidate:main-<fedora>-<kernel_release>`
3. Stable OS image: `ghcr.io/danathar/kinoite-zfs:latest`
4. Stable OS audit tag: `ghcr.io/danathar/kinoite-zfs:stable-<run>-<sha>`
5. Stable akmods cache image: `ghcr.io/danathar/akmods-zfs:main-<fedora>`

### Branch Artifacts

1. OS image: `ghcr.io/danathar/kinoite-zfs:br-<branch>-<fedora>` (BlueBuild branch tag pattern)
2. Akmods cache image: `ghcr.io/danathar/akmods-zfs-<branch>:main-<fedora>`

Branch artifacts are isolated by both tag and repo name to avoid clobbering main caches.

## End-To-End Build Flow

### 1. Detect Base Kernel Stream

The main workflow resolves build inputs in one of two modes:

1. Default mode: resolve floating refs (for example `kinoite-main:latest`) to immutable digests and immutable stream tags at run time.
2. Replay mode: read pinned inputs from [`ci/inputs.lock.json`](../ci/inputs.lock.json) when `use_input_lock=true`.

After resolving the base image ref, it reads `ostree.linux` to obtain:

1. The full kernel release (example: `6.18.12-200.fc43.x86_64`).
2. Fedora major version (example: `43`).

This ensures akmods cache and final image build both align to the same kernel stream, even if `latest` advances during the workflow run.

The workflow also writes a `build-inputs-<run_id>` artifact containing all resolved inputs (base image digest, builder digest, kernel, ZFS line, and akmods ref) for audit and replay.

### 2. Validate Existing Candidate Akmods Cache

Before rebuilding akmods, CI checks whether the existing candidate cache image already contains:

1. `kmod-zfs-<exact-kernel-release>-*.rpm` for the current base kernel.

If a matching RPM exists, akmods rebuild is skipped.
If missing, akmods rebuild is forced.

This is the core mechanism that prevents shipping stale kmods.

### 3. Build Candidate Akmods (When Required)

If cache is missing/stale (or manual rebuild is requested), CI:

1. Fetches a pinned commit from the maintained fork (`Danathar/akmods`).
2. Pulls OpenZFS release source from upstream OpenZFS GitHub releases (`https://github.com/openzfs/zfs/releases`) through the akmods build scripts.
3. Injects the ZFS image target under this repo owner namespace (the owner/org part of the image path, like `danathar` in `ghcr.io/danathar/...`).
4. Seeds upstream akmods cache metadata with the resolved `KERNEL_RELEASE`.
5. Builds and publishes kernel-matched akmods tags.

### 4. Build Candidate Kinoite Image

[`recipes/recipe.yml`](../recipes/recipe.yml) and [`containerfiles/zfs-akmods/Containerfile`](../containerfiles/zfs-akmods/Containerfile) are rewritten in-run to pin base + akmods inputs, then:

1. Pins `base-image`/`image-version` to the resolved immutable base tag from input resolution.
2. Pulls the akmods cache image for the resolved kernel release.
3. Extracts ZFS RPMs from image layers.
4. Installs RPMs via `rpm-ostree install`.
5. Verifies `/lib/modules/<kernel>/extra/zfs/zfs.ko` exists for each base kernel.
6. Runs `depmod -a <kernel>` to ensure module dependency metadata is generated in build context.

If module files do not match kernel directories, candidate build fails immediately.

### 5. Promote Candidate To Stable

Promotion runs only after successful candidate akmods and candidate image jobs:

1. Retags candidate image to stable `latest`.
2. Publishes immutable stable audit tag (`stable-<run>-<sha>`).
3. Aligns stable akmods tag (`main-<fedora>`) to the candidate akmods source cache image.

If candidate fails, promotion does not run, and the previous stable tags remain unchanged.

### Why This Is Safer

This two-step model (candidate build, then promotion) protects stable users:

1. Candidate is where new upstream changes are exercised first.
2. Promotion is the only step allowed to move stable tags.
3. If candidate fails for any reason, stable tags do not move.

In practice, this means:

1. A bad nightly build does not overwrite `latest`.
2. The system keeps serving the last known-good stable image.
3. You get fast feedback on breakage without forcing users onto broken outputs.

## Workflow Behavior

### [`.github/workflows/build.yml`](../.github/workflows/build.yml) (Main)

Triggers:

1. Push to `main`.
2. Nightly schedule.
3. Manual dispatch.

Key behavior:

1. Builds/publishes kernel-matched akmods cache tags as needed.
2. Builds/publishes candidate image.
3. Promotes candidate artifacts to stable tags only on success.
4. Manual dispatch supports candidate-only runs by setting `promote_to_stable=false`.
5. Manual dispatch supports lock replay (`use_input_lock=true`) with pinned refs from [`ci/inputs.lock.json`](../ci/inputs.lock.json).
6. Uploads a per-run build input manifest artifact (`build-inputs-<run_id>`).
7. Ignores markdown/docs-only changes.

### [`.github/workflows/build-beta.yml`](../.github/workflows/build-beta.yml) (Branch)

Triggers:

1. Push to non-main branches.
2. Manual dispatch.

Key behavior:

1. Computes branch-safe image tag and branch-specific akmods repo name.
2. Builds/publishes branch-isolated akmods cache as needed.
3. Rewrites [`recipes/recipe.yml`](../recipes/recipe.yml) in-run to consume branch-scoped akmods source.
4. Builds/publishes branch-tagged image.
5. Ignores markdown/docs-only changes.

### [`.github/workflows/build-pr.yml`](../.github/workflows/build-pr.yml) (PR Validation)

Triggers:

1. Pull request updates.

Key behavior:

1. Build only; no push.
2. No signing requirement.
3. Ignores markdown/docs-only changes.

## Kernel Compatibility Risk Handling

Real-world discussion context:

1. https://github.com/ublue-os/aurora/issues/1765
2. https://github.com/ublue-os/aurora/issues/1765#issuecomment-3967188245

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

This section is updated for each tracked issue as we work through hardening items (safety improvements that reduce breakage risk).
For each new issue, add a section with:

1. Problem
2. Mitigation implemented
3. Residual risk
4. Planned follow-up

## Issue #1: Upstream Source Drift In Akmods Tooling

Problem:

1. Building from floating `ublue-os/akmods` `main` can break unexpectedly if upstream scripts change.
2. Previously, runtime workflow patches introduced additional drift and fragility.

Mitigation implemented:

1. Pin akmods source to explicit fork commit:
   - Repo: `https://github.com/Danathar/akmods`
   - Ref: `9d13b6950811cdaae2e8ab748c85c5da35810ae3`
2. Fetch exactly that commit and verify resolved SHA matches expected.
3. Use the same pin in both main and branch workflows for deterministic behavior.

Where:

1. [`.github/workflows/build.yml`](../.github/workflows/build.yml)
2. [`.github/workflows/build-beta.yml`](../.github/workflows/build-beta.yml)

Residual risk:

1. Pinned commit can become outdated for future Fedora/ZFS changes.
2. Manual pin updates are still required when moving to newer upstream akmods logic.

Planned follow-up:

1. Maintain fork update process documented in [`docs/akmods-fork-maintenance.md`](./akmods-fork-maintenance.md).

## Issue #2: No Compatibility Holdback When Fedora Kernel Jumps Ahead

Problem:

1. Main builds intentionally track `kinoite-main:latest` and therefore track new Fedora kernels quickly.
2. When Fedora publishes a kernel before OpenZFS/akmods is compatible, builds can fail until upstream support catches up.
3. There is currently no explicit holdback/freeze mechanism in this repo to keep publishing a known-good compatible stream during that window.

Mitigation implemented:

1. Implemented candidate-first pipeline in [`.github/workflows/build.yml`](../.github/workflows/build.yml).
2. Main workflow now publishes candidate artifacts before touching stable tags.
3. Added gated promotion job that retags candidate artifacts to stable only when candidate jobs succeed.
4. Added manual dispatch input `promote_to_stable` for controlled candidate-only runs.

Where:

1. [`.github/workflows/build.yml`](../.github/workflows/build.yml)

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

1. Added lock replay inputs to [`.github/workflows/build.yml`](../.github/workflows/build.yml) (`use_input_lock`, `lock_file`, `build_container_image`).
2. Added deterministic input resolution step that records immutable digests for base image and builder container.
3. Candidate image flow now pins `base-image`/`image-version` to a resolved immutable base tag, rewrites `AKMODS_IMAGE` to a kernel-matched tag, and validates exact-module presence.
4. Added build input manifest artifact upload (`build-inputs-<run_id>`) for audit and reproducible reruns.
5. Added repository lock file [`ci/inputs.lock.json`](../ci/inputs.lock.json) for replay mode.
6. Akmods build now seeds upstream cache metadata (`cache.json`) from resolved `KERNEL_RELEASE`.

Where:

1. [`.github/workflows/build.yml`](../.github/workflows/build.yml)
2. [`ci/inputs.lock.json`](../ci/inputs.lock.json)

Residual risk:

1. Default scheduled/push runs still follow moving upstream inputs by design (to catch breakage early).
2. Replay mode requires operator discipline to keep [`ci/inputs.lock.json`](../ci/inputs.lock.json) aligned with a selected run artifact.
3. ZFS version is still pinned at minor line unless replay lock sets a different value.

Planned follow-up:

1. Add OCI labels with resolved input metadata to published candidate/stable images.
2. Add a helper script to auto-sync [`ci/inputs.lock.json`](../ci/inputs.lock.json) from a selected run artifact.

## Issue #4: Runtime Patching Is Operationally Fragile

Problem:

1. Runtime script patching (`sed`/`perl`) is fragile and can break when upstream script layout changes.
2. Each upstream packaging change can force emergency workflow patch updates.
3. Even with guardrails, this creates avoidable maintenance churn in CI.

Mitigation implemented:

1. Created and pinned a maintained fork source: `https://github.com/Danathar/akmods`.
2. Added required dependency fixes directly in fork commit `9d13b6950811cdaae2e8ab748c85c5da35810ae3`:
   - `jq` install in `build_files/zfs/build-kmod-zfs.sh`
   - `python3-cffi` in `build_files/prep/build-prep.sh`
3. Updated [`.github/workflows/build.yml`](../.github/workflows/build.yml) and [`.github/workflows/build-beta.yml`](../.github/workflows/build-beta.yml) to pin `AKMODS_UPSTREAM_REPO`/`AKMODS_UPSTREAM_REF` to that fork commit.
4. Removed runtime patch injection logic from both workflows.
5. Added operator maintenance guide: [`docs/akmods-fork-maintenance.md`](./akmods-fork-maintenance.md).

Residual risk:

1. Fork still requires periodic refresh/rebase against upstream `ublue-os/akmods`.
2. Pin updates remain an operator responsibility.

Planned follow-up:

1. Upstream forked changes to `ublue-os/akmods` where possible.
2. When upstream contains the required fixes, repoint pin to upstream commit and retire fork delta.

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

1. Rebase to test image (switch the VM to boot from the test image ref).
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
