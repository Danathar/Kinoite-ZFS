# Kinoite-ZFS Architecture Overview

## Purpose

This project provides a controlled way to run ZFS on Kinoite while reducing the risk of breakage from upstream kernel changes.

## Quick Terms

1. Candidate: a test build. It is built first and checked before anything is marked stable.
2. Stable: the tags users should normally consume (`latest` and `main-<fedora>`).
3. Workflow metadata: run details like run ID, branch/ref, commit SHA, and triggering user.
4. Image ref: a container image pointer, usually `name:tag` (moving) or `name@sha256:digest` (exact).
5. Build inputs: base image, kernel, builder image, and pinned source commit used for one run.
6. Lock replay: rerun using saved inputs from a previous run.

## Beginner Primer: Akmods On Atomic Images

1. `akmods` means "automatic kernel module packaging/build flow" used for modules not shipped in the base kernel tree.
2. On image-based systems (Kinoite/Aurora), we want module compatibility solved in the build pipeline, not by ad-hoc client-side fixes.
3. This repo builds and validates kernel-matching ZFS module RPMs first, then installs them into the image build.
4. Candidate-first promotion means stable users only get images from runs that already passed those checks.

At a high level, this repository has a build workflow that:

1. Tracks the current Fedora/Kinoite kernel stream.
2. Builds ZFS kernel modules (`kmod-zfs`) for that kernel.
3. Integrates those modules into a custom Kinoite image.
4. Publishes to stable tags only after checks pass.

## What We Are Doing

We publish two output groups:

1. Candidate outputs (test stage):
   - Run-scoped image source tag produced by BlueBuild (`<shortsha>-<fedora>`)
   - Kernel-matched akmods source tag: `ghcr.io/danathar/akmods-zfs:main-<fedora>-<kernel_release>`
2. Stable outputs (updated only after candidate success):
   - `ghcr.io/danathar/kinoite-zfs:latest`
   - `ghcr.io/danathar/akmods-zfs:main-<fedora>`

Branch builds are isolated (`beta-*` tags and branch-specific akmods repos) so experiments do not overwrite stable images.

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
4. Kernel/Fedora version metadata.
5. Pinned akmods fork source commit.
6. ZFS version line.

These inputs are saved as a file (`build-inputs-<run_id>`) so you can inspect what that run used.

### 2. Candidate Akmods Build

The workflow checks cached akmods images for a `kmod-zfs` RPM that matches the exact kernel release.

1. If yes, it reuses cache.
2. If no, it rebuilds and publishes kernel-matched akmods tags.

This avoids publishing images with outdated kernel modules.

### 3. Candidate Image Build

The workflow rewrites recipe/containerfile inputs before candidate compose to:

1. Pin `base-image` + `image-version` to the resolved immutable base tag for this run.
2. Use a kernel-matched akmods tag (`main-<fedora>-<kernel_release>`).

The build validates ZFS module presence for kernel directories before image publish.

### 4. Promotion To Stable

Promotion is a separate gated job:

1. Runs only after candidate jobs succeed.
2. Retags run-scoped candidate image source to stable `latest`.
3. Aligns stable akmods tag (`main-<fedora>`) to the selected source image.
4. Writes an immutable stable audit tag (`stable-<run>-<sha>`).

If candidate fails, stable tags are not changed.

### 5. Replay Mode

For repeatable troubleshooting, manual runs support lock replay using [`ci/inputs.lock.json`](../ci/inputs.lock.json).

This lets you rebuild with saved values instead of moving `latest` tags.

## Operational Model

1. `main` workflow (`build.yml`): candidate build + gated promotion.
2. Branch workflow (`build-beta.yml`): isolated branch testing.
3. PR workflow (`build-pr.yml`): validation only, no push.

## Implementation Note: Workflow Scripts

Workflow entry-point scripts under `.github/scripts/main`, `.github/scripts/beta`, and `.github/scripts/akmods` are thin shell wrappers.
The behavior lives in Python modules under `ci_tools/`.

Why this setup:

1. Keep workflow YAML focused on job wiring.
2. Keep logic in code that is easier to read and unit-test.
3. Preserve existing workflow step paths (`.sh` files) so workflow YAML stays stable.

Term note used in code/docs:

1. Normalize owner/org name means convert it to lowercase before building image paths (example: `Danathar` -> `danathar`).

## Design Principles

1. Safety first: never advance stable on candidate failure.
2. Isolation: separate candidate, branch, and stable artifacts.
3. Visibility: save exact input metadata every run.
4. Repeatability: support lock replay for troubleshooting.
5. Incremental hardening: address risks issue-by-issue and document each mitigation.

## Related Documents

1. Detailed technical runbook and issue log: [`docs/zfs-kinoite-testing.md`](./zfs-kinoite-testing.md)
2. Akmods fork update process: [`docs/akmods-fork-maintenance.md`](./akmods-fork-maintenance.md)
3. Project quickstart and usage: [`README.md`](../README.md)
