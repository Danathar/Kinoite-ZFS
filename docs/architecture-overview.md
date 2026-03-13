# Kinoite-ZFS Architecture Overview

If a term is unfamiliar, check the shared glossary first:
[`docs/glossary.md`](./glossary.md)

## Purpose

This project provides a controlled way to run ZFS on Kinoite while reducing the risk of breakage from upstream kernel changes.

It is also intended to be reusable:

1. Current implementation targets Kinoite-based images.
2. The workflow structure can be adapted for other Universal Blue or Fedora Atomic image streams when users want to keep ZFS support.

## Real-World Context

Discussion reference:

1. https://github.com/ublue-os/aurora/issues/1765
2. https://github.com/ublue-os/aurora/issues/1765#issuecomment-3967188245

Beginner summary:

1. The hard part is kernel timing, not simply "immutable images."
2. Fedora-family images move kernels quickly.
3. ZFS is out-of-tree, so OpenZFS support can lag new kernels.
4. That timing gap creates risk of module mismatch unless builds are gated carefully.

This repo's pipeline is designed around that exact problem.

## Beginner Primer: Akmods On Atomic Images

1. `akmods` means "automatic kernel module packaging/build flow" used for modules not shipped in the base kernel tree.
2. On image-based systems (Kinoite/Aurora), we want module compatibility solved in the build pipeline, not by ad-hoc client-side fixes.
3. This repo builds and validates kernel-matching ZFS module RPMs first, then installs them into the image build.
4. Candidate-first promotion means stable users only get images from runs that already passed those checks.

At a high level, this repository has a build workflow that:

1. Tracks the current Fedora/Kinoite kernel stream (the moving sequence of new kernel versions over time).
2. Builds ZFS kernel modules (`kmod-zfs`) for the kernel set shipped in that base image.
3. Integrates those modules into a custom Kinoite image.
4. Publishes to stable tags only after checks pass.

## What We Are Doing

We publish two output groups:

1. Candidate outputs (test stage):
   - Run-scoped image source tag in candidate repo: `ghcr.io/danathar/kinoite-zfs-candidate:<shortsha>-<fedora>`
   - Candidate akmods cache tag used by compose: `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods-candidate:main-<fedora>`
   - Newest-kernel candidate akmods debug tag: `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods-candidate:main-<fedora>-<kernel_release>`
2. Stable outputs (updated only after candidate success):
   - `ghcr.io/danathar/kinoite-zfs:latest`
   - `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-<fedora>`

Branch builds are isolated (`br-<branch>-<fedora>` tags on branch image outputs plus branch-scoped akmods alias tags in candidate repo) so experiments do not overwrite stable images.

## Why We Are Doing It

ZFS support can lag behind new Fedora kernels. Without controls, a fast-moving kernel stream can produce broken images.

This architecture addresses that risk by:

1. Testing compatibility in candidate first.
2. Keeping stable tags unchanged when candidate fails.
3. Recording exact build inputs so runs can be investigated and repeated.
4. Keeping a clear separation between test builds and stable user-facing tags.

### Why Candidate-First Helps Safety

Candidate-first + promotion is a safety gate:

1. The workflow builds and tests candidate outputs first.
2. Only if that test build succeeds does the promotion job update stable tags.
3. If candidate fails, stable tags are left as-is.

Why this matters for this project:

1. Kernel and ZFS compatibility can break suddenly when upstream updates.
2. A failed candidate run blocks a broken image from replacing `latest`.
3. Users who consume stable tags stay on the last known-good build until a new good build is ready.

## How It Works

### 1. Input Resolution

The main workflow resolves build inputs for each run:

1. Base image (Kinoite) and its immutable digest.
2. Base image immutable stream tag (for BlueBuild `image-version` pinning).
3. Build container image and digest.
4. Kernel/Fedora version metadata, including every installed kernel directory from `/lib/modules`.
5. Pinned akmods fork source commit.
6. ZFS version line.

These inputs are saved as a file (`build-inputs-<run_id>`) so you can inspect what that run used.

### 2. Candidate Akmods Build

The workflow checks cached akmods images for `kmod-zfs` RPMs that match every kernel shipped in the pinned base image.

1. If yes, it reuses cache.
2. If no, it rebuilds and publishes the Fedora-wide cache again so it contains RPMs for every installed base-image kernel.
3. During rebuild, the akmods tooling pulls OpenZFS release source from the upstream OpenZFS GitHub releases page (`https://github.com/openzfs/zfs/releases`).
4. In multi-kernel rebuilds, the wrapper gives each kernel its own cache path first, because upstream akmods assumes one kernel payload per cache directory.
5. The wrapper then publishes each kernel-specific image tag and merges those local outputs into one shared Fedora-wide cache image (`main-<fedora>`).
6. That same multi-kernel path disables Buildah layer caching so each kernel build sees its own mounted RPM cache instead of reusing stale filesystem layers from the previous kernel iteration.

### Deferred Refactor Note

The current shared-image merge is a compatibility layer around upstream akmods behavior.

Why we do it this way today:

1. It preserves the existing downstream contract: candidate compose, promotion, branch aliasing, and manual switching can keep reading one shared `main-<fedora>` tag.
2. It keeps the change surface small while upstream base images may carry more than one installed kernel.

If we later choose a broader refactor, the main alternative is:

1. Stop publishing one shared cache image.
2. Teach candidate/stable consumers to read multiple kernel-specific akmods tags directly.

That broader design may be cleaner long term, but it would require coordinated changes across compose inputs, cache checks, alias publishing, promotion logic, and operator documentation.

This avoids publishing images with outdated kernel modules.

### 3. Candidate Image Build

The workflow now creates a generated build workspace before candidate compose
(candidate image build stage).

`Generated build workspace` here means a transient directory created during CI
that BlueBuild treats as its local working directory for this one run.

Within that generated workspace, the workflow:

1. Pin `base-image` + `image-version` to the resolved immutable base tag for this run.
2. Use the candidate-repo Fedora-wide akmods cache tag (`main-<fedora>`), which can carry RPMs for more than one installed kernel.
3. Normalize signature trust policy entries after the signing module so both
   stable and candidate repo names are trusted in the final image:
   - `ghcr.io/danathar/kinoite-zfs`
   - `ghcr.io/danathar/kinoite-zfs-candidate`

The canonical repo files stay unchanged. The build action's `working_directory`
input points at that generated workspace instead of the checked-in repo root.

The build validates ZFS module presence for kernel directories before image publish.

When the base image carries more than one installed kernel, candidate compose uses
two install paths on purpose:

1. Shared userspace ZFS RPMs and one primary `kmod-zfs` RPM still go through
   `rpm-ostree install`.
2. Additional kernel-specific `kmod-zfs` RPM payloads are unpacked directly into
   the image root and then `depmod -a <kernel>` runs for each base kernel.
3. The compose-time RPM/kernel mapping now lives in
   [containerfiles/zfs-akmods/install_zfs_from_akmods_cache.py](/var/home/dbaggett/git/zfs_migration/containerfiles/zfs-akmods/install_zfs_from_akmods_cache.py)
   instead of one long inline shell block, so the multi-kernel workaround can be
   unit-tested separately from the Containerfile wrapper.

Why this exists:

1. The akmods cache can hold multiple `kmod-zfs-<kernel_release>` RPM files.
2. Those RPM files still share one internal RPM identity (`kmod-zfs`), so
   `rpm-ostree` does not keep them installed side-by-side as distinct packages.
3. Direct payload extraction is the current repo-side compatibility shim that
   keeps every shipped kernel directory populated until we decide whether a
   broader downstream refactor is worth it.

### 4. Promotion To Stable

Promotion is a separate gated job:

1. Runs only after candidate jobs succeed.
2. Retags run-scoped candidate image source to stable `latest`.
3. Aligns stable akmods tag (`main-<fedora>`) to the candidate akmods source image.
4. Writes an immutable stable audit tag (`stable-<run>-<sha>`).
5. Re-signs the promoted stable image digest so signature-required host rebases continue to work.
6. Relies on the in-image policy normalization from compose time so signed host
   switches can move between candidate and stable repository names.

The promotion job now uses one local composite action for its repeated workflow
glue:
[`.github/actions/promote-stable/action.yml`](../.github/actions/promote-stable/action.yml)

That local action still calls the same Python helpers:

1. [`ci_tools/main_promote_stable.py`](../ci_tools/main_promote_stable.py)
2. [`ci_tools/main_sign_promoted_stable.py`](../ci_tools/main_sign_promoted_stable.py)

If candidate fails, stable tags are not changed.

### 5. Replay Mode

For repeatable troubleshooting, manual runs support lock replay using [`ci/inputs.lock.json`](../ci/inputs.lock.json).

This lets you rebuild with saved values instead of moving `latest` tags.

## Operational Model

1. `main` workflow (`build.yml`): candidate build + gated promotion.
2. Branch workflow (`build-beta.yml`): isolated branch testing.
3. PR workflow (`build-pr.yml`): validation only, no push.
4. Branch and PR workflows now share one read-only validation prep wrapper before compose, so both paths pin the same inputs and fail closed on stale shared akmods caches.
5. `main` now uses one local main-prep wrapper before rebuild decisions, so input resolution, build-input artifact upload, and shared-cache inspection stay wired together.

## Implementation Note: Workflow Scripts

Workflow jobs call Python commands directly (`python3 -m ci_tools.cli <command>`)
and also use local composite actions for the repeated workflow glue:

1. BlueBuild compose wrapper:
   [`.github/actions/run-bluebuild/action.yml`](../.github/actions/run-bluebuild/action.yml)
2. Main input/cache prep wrapper:
   [`.github/actions/prepare-main-build-inputs/action.yml`](../.github/actions/prepare-main-build-inputs/action.yml)
3. Stable-promotion wrapper:
   [`.github/actions/promote-stable/action.yml`](../.github/actions/promote-stable/action.yml)
4. Validation-prep wrapper:
   [`.github/actions/prepare-validation-build/action.yml`](../.github/actions/prepare-validation-build/action.yml)
5. Generated-workspace wrapper:
   [`.github/actions/configure-generated-build-context/action.yml`](../.github/actions/configure-generated-build-context/action.yml)

The behavior lives in Python modules under `ci_tools/` plus those local
workflow helper actions.

Why this setup:

1. Keep workflow YAML focused on job wiring.
2. Keep logic in code that is easier to read and unit-test.
3. Keep workflow command dispatch centralized in one CLI entrypoint.
4. Keep repeated workflow wiring in local reusable actions instead of copying the same setup/install/configure blocks across workflow files.

Term note used in code/docs:

1. Normalize owner/org name means convert it to lowercase before building image paths (example: `Danathar` -> `danathar`).

## Design Principles

1. Safety first: never advance stable on candidate failure.
2. Isolation: separate candidate, branch, and stable artifacts.
3. Visibility: save exact input metadata every run.
4. Repeatability: support lock replay for troubleshooting.
5. Incremental hardening (step-by-step safety tightening): address risks issue-by-issue and document each mitigation.

## Related Documents

1. Detailed technical runbook and issue log: [`docs/zfs-kinoite-testing.md`](./zfs-kinoite-testing.md)
2. Akmods fork update process: [`docs/akmods-fork-maintenance.md`](./akmods-fork-maintenance.md)
3. Step-by-step code walkthrough: [`docs/code-reading-guide.md`](./code-reading-guide.md)
4. Project quickstart and usage: [`README.md`](../README.md)
