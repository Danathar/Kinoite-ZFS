# Kinoite-ZFS Architecture Overview

## Purpose

This project provides a controlled way to run ZFS on Kinoite while reducing the risk of breakage from upstream kernel changes.

At a high level, the repository is a release pipeline that:

1. Tracks the current Fedora/Kinoite kernel stream.
2. Builds ZFS kernel modules (`kmod-zfs`) for that kernel.
3. Integrates those modules into a custom Kinoite image.
4. Publishes only validated outputs to stable tags.

## What We Are Doing

We build and publish two classes of artifacts:

1. Candidate artifacts (pre-promotion):
   - Run-scoped image source tag produced by BlueBuild (`<shortsha>-<fedora>`)
   - Kernel-matched akmods source tag: `ghcr.io/danathar/akmods-zfs:main-<fedora>-<kernel_release>`
2. Stable artifacts (promoted only after candidate success):
   - `ghcr.io/danathar/kinoite-zfs:latest`
   - `ghcr.io/danathar/akmods-zfs:main-<fedora>`

Branch builds are isolated (`beta-*` tags and branch-specific akmods repos) so experimentation does not overwrite stable images.

## Why We Are Doing It

ZFS support can lag behind new Fedora kernels. Without controls, a fast-moving kernel stream can create broken images or operational outages.

This architecture addresses that risk by:

1. Testing compatibility in candidate first.
2. Keeping stable tags unchanged when candidate fails.
3. Recording exact build inputs for audit and reproducible replay.
4. Preserving a clear promotion boundary between testing and production consumption.

## How It Works

### 1. Input Resolution

The main workflow resolves build inputs for each run:

1. Base image (Kinoite) and its immutable digest.
2. Build container image and digest.
3. Kernel/Fedora version metadata.
4. Pinned akmods fork source commit.
5. ZFS version line.

These inputs are captured as an artifact (`build-inputs-<run_id>`) for traceability.

### 2. Candidate Akmods Build

The pipeline checks cache sources for a `kmod-zfs` RPM matching the exact kernel release.

1. If yes, it reuses cache.
2. If no, it rebuilds and publishes kernel-matched akmods tags.

This avoids publishing images with stale kernel modules.

### 3. Candidate Image Build

The workflow rewrites only the ZFS `AKMODS_IMAGE` reference in `containerfiles/zfs-akmods/Containerfile` to:

1. Use a kernel-matched akmods tag (`main-<fedora>-<kernel_release>`).
2. Keep recipe `base-image`/`image-version` unchanged for BlueBuild parsing compatibility.

The build validates ZFS module presence for kernel directories before image publish.

### 4. Promotion To Stable

Promotion is a separate gated job:

1. Runs only after candidate jobs succeed.
2. Retags run-scoped candidate image source to stable `latest`.
3. Aligns stable akmods tag (`main-<fedora>`) to the selected source image.
4. Writes an immutable stable audit tag (`stable-<run>-<sha>`).

If candidate fails, promotion is skipped and existing stable tags remain untouched.

### 5. Replay Mode

For deterministic reproduction, manual dispatch supports lock-based replay using `ci/inputs.lock.json`.

This allows rebuilding with pinned refs instead of floating `latest` sources.

## Operational Model

1. `main` workflow (`build.yml`): candidate build + gated promotion.
2. Branch workflow (`build-beta.yml`): isolated branch testing.
3. PR workflow (`build-pr.yml`): validation only, no push.

## Design Principles

1. Safety first: never advance stable on candidate failure.
2. Isolation: separate candidate, branch, and stable artifacts.
3. Observability: capture immutable input metadata every run.
4. Reproducibility: support lock-based replay for incident/debug workflows.
5. Incremental hardening: address risks issue-by-issue and document each mitigation.

## Related Documents

1. Detailed technical runbook and issue log: `docs/zfs-kinoite-testing.md`
2. Akmods fork update process: `docs/akmods-fork-maintenance.md`
3. Project quickstart and usage: `README.md`
