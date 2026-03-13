# Kinoite-ZFS

[![Build Main Image](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml/badge.svg)](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml)

> [!NOTE]
> This repository was developed almost entirely with AI assistance. I was more a conductor than a player on this thing. I think anyone using open-source tools on GitHub should have that context before relying on them.
>
> This was as much about having fun on a Friday afternoon with AI as it was about seeing whether this idea could be done. Treat it as such. Please do not use this in production for **ANYTHING**.
>
> This repo is **THE** definition of *brittle*! Honestly, it's probably FAR easier to do what groups like Universal Blue do and manually track and hold back releases until the correct ZFS release is available than to maintain this insane bit of code the AI has tried to make while covering all possibilities.
>
> It is probably WAY more complicated than it needs to be. I'm still reading through the code it made. That said, it does work, seemingly. ;)

This repository exists to test and validate ZFS support on Kinoite images built with BlueBuild.

> [!WARNING]
> This repository is wired to a dedicated local self-hosted GitHub Actions runner.
> Do not template or fork it as-is unless you are also replacing that runner
> configuration in [`.github/workflows/build.yml`](.github/workflows/build.yml)
> and [`.github/workflows/build-beta.yml`](.github/workflows/build-beta.yml).
> The PR workflow intentionally stays on GitHub-hosted runners, but trusted
> branch and main builds now expect the `kinoite-zfs-builder` runner label.
>
> If you want a repo to fork or template, use
> [`Danathar/zfs-kinoite-containerfile`](https://github.com/Danathar/zfs-kinoite-containerfile)
> instead. That is the newer repo for this project direction.
>
> If you still want to adapt this old BlueBuild repo to your own dedicated
> Bluefin self-hosted runner VM, read
> [`docs/self-hosted-runner.md`](docs/self-hosted-runner.md) first and replace
> the repo scope, runner labels, and GHCR package names deliberately.
>
> This BlueBuild repo also uses its own dedicated akmods package names so it no
> longer shares the `akmods-zfs` GHCR cache namespace with that newer repo.

If you are new to ZFS:

- ZFS is a filesystem + volume manager focused on data integrity and storage management features (for example checksums, snapshots, and pooled storage).
- In this repo, the key detail is that ZFS needs kernel modules that must match the running kernel version.
- Owner opinion around here: ZFS is awesome and everyone should use it :)

Core goal:

- Track the current Kinoite/Fedora kernel stream (stream = the moving sequence of kernel versions published over time, newest to oldest).
- Build matching ZFS akmods against that kernel.
- Install those ZFS RPMs directly into the final image.
- Catch kernel/module mismatches during CI (automated GitHub Actions workflow runs), before rebasing a host (`rebasing` here means switching an existing atomic host to a newly built container image).
- Keep the workflow maintainable for this repository's own image stream.

## If You Are New To Akmods And Atomic Images

`akmod` (automatic kernel module) packages are a way to provide out-of-tree
kernel modules (`out-of-tree` means the module is developed outside the Linux
kernel source tree and shipped separately), like ZFS, for a specific kernel
release.

Why this matters here:

1. Kinoite/Aurora-style systems are image-based and mostly immutable.
2. You usually do not want ad-hoc module build steps happening directly on every client machine.
3. Instead, we build and validate matching ZFS kernel modules in our pipeline (the ordered set of build/check/publish steps in one workflow run), then bake those RPMs into the final image.

In plain terms, this project is doing:

1. Read current upstream kernel version from labels stored in Kinoite base image metadata (extra descriptive data attached to the image).
2. Build (or reuse) ZFS akmods that exactly match that kernel.
3. For new builds, akmods pulls OpenZFS source from upstream OpenZFS GitHub releases (`https://github.com/openzfs/zfs/releases`) and builds RPMs from that release source.
4. Build a candidate custom image (`candidate` = test image built first) that installs those ZFS RPMs.
5. Promote to stable tags (`stable` = normal user-facing tags) only if candidate build/test checks succeed.

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
3. A practical goal of this repository is continuity for this specific image stream if upstream image defaults change.

If you are new to some of the terms used below, read the glossary first:

- [`docs/glossary.md`](docs/glossary.md)

If you want the full technical design and workflow details, read:

- [`docs/documentation-guide.md`](docs/documentation-guide.md) (documentation tree and reading paths by goal)
- [`docs/code-reading-guide.md`](docs/code-reading-guide.md) (step-by-step file reading order for newcomers)
- [`docs/architecture-overview.md`](docs/architecture-overview.md) (high-level architecture: what/why/how)
- [`docs/upstream-change-response.md`](docs/upstream-change-response.md) (user/operator failure response guide)
- [`docs/akmods-fork-maintenance.md`](docs/akmods-fork-maintenance.md) (how to maintain and update the pinned akmods fork source)
- [`docs/zfs-kinoite-testing.md`](docs/zfs-kinoite-testing.md)
- [`.github/scripts/README.md`](.github/scripts/README.md) (workflow command map: step -> command -> Python module)

[`docs/zfs-kinoite-testing.md`](docs/zfs-kinoite-testing.md) is maintained as a living record and is updated as each hardening issue (each safety-improvement task) is addressed.

## What Gets Published

- Candidate image (pre-promotion):
  - `ghcr.io/danathar/kinoite-zfs-candidate:<shortsha>-<fedora>`
- Candidate akmods cache image (pre-promotion):
  - `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods-candidate:main-<fedora>`
- Stable image (promoted only after candidate success):
  - `ghcr.io/danathar/kinoite-zfs:latest`
- Stable image audit tag (immutable per promotion):
  - `ghcr.io/danathar/kinoite-zfs:stable-<run>-<sha>`
- Stable akmods cache image (promoted from candidate cache):
  - `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-<fedora>`
- Branch test image:
  - `ghcr.io/danathar/kinoite-zfs:br-<branch>-<fedora>` (BlueBuild branch tag pattern)
- Shared akmods source tag used by branch alias step:
  - `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-<fedora>`
- Branch akmods compose alias (branch-scoped public tag):
  - `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods-candidate:br-<branch>-<fedora>`

Candidate and branch artifacts are isolated so test runs do not overwrite stable `ghcr.io/danathar/kinoite-zfs:latest`.

## Why Candidate First

This repo uses a two-step safety model:

1. Build/test candidate outputs first.
2. Promote to stable tags only if candidate succeeds.

If candidate fails, stable tags are not updated. That protects users from overnight upstream breakage and keeps stable on the last known-good build.

## Workflows

- [`.github/workflows/build.yml`](.github/workflows/build.yml)
  - Builds candidate artifacts first, then promotes them to stable tags on success.
  - Copies shared akmods source tags into candidate akmods tags before candidate compose (candidate image build step) and promotion.
  - Re-signs the promoted stable image digest after copy, because signatures are repository-specific and do not automatically move from `kinoite-zfs-candidate` to `kinoite-zfs`.
  - Normalizes in-image signature policy after signing so both repository names are trusted.
    - “Policy entries” here means repository-specific trust rules written to:
      - `/etc/containers/policy.json` (signature verification rules)
      - `/etc/containers/registries.d/*.yaml` (where to find sigstore attachments)
    - The two repository rules are:
    - `ghcr.io/danathar/kinoite-zfs`
    - `ghcr.io/danathar/kinoite-zfs-candidate`
  - Pins candidate compose to a resolved immutable base image tag per run to avoid mid-run `latest` drift.
  - Calls Python workflow helpers in `ci_tools/` directly through `python3 -m ci_tools.cli <command>`.
  - Runs on `main` pushes, nightly schedule, and manual dispatch.
  - Uploads a `build-inputs-<run_id>` artifact capturing exact resolved build inputs.
- [`.github/workflows/build-beta.yml`](.github/workflows/build-beta.yml)
  - Builds branch-tagged test artifacts for non-main branches.
  - Copies shared akmods source tags into branch-scoped public alias tags in `kinoite-zfs-bluebuild-akmods-candidate` for compose (branch image build step).
  - Fails closed if shared akmods source tags are missing/stale (so test branches do not mutate shared cache tags).
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

### Fresh Stock Kinoite Install

On a fresh stock Kinoite install, you can switch directly:

```bash
sudo bootc switch ghcr.io/danathar/kinoite-zfs:latest
systemctl reboot
```

Why this works:

1. `bootc switch` evaluates trust policy on the currently booted host before it imports the target image.
2. Fresh stock Kinoite does not ship a repo-specific signature requirement for `ghcr.io/danathar/kinoite-zfs`.
3. After the first boot into this image family, the in-image trust config is available for later signed stable/candidate moves.

### Older Already-Booted Repo Images

If you are already running one of this repo's older images and `bootc switch` or
`bootc upgrade` fails with signature-policy errors, repair the host trust config
once and retry:

```bash
sudo ./scripts/fix-host-signing-policy.sh
sudo bootc switch ghcr.io/danathar/kinoite-zfs:latest
systemctl reboot
```

Hosts booted into images built before March 7, 2026 are the main case that may
need that one-time repair.

### Signed Bootstrap Alternative

If you prefer an explicit unverified bootstrap first, this still works:

Here, "rebase" means "tell rpm-ostree to switch this machine to boot from a new image reference."

```bash
rpm-ostree rebase ostree-unverified-registry:ghcr.io/danathar/kinoite-zfs:latest
systemctl reboot
rpm-ostree rebase ostree-image-signed:docker://ghcr.io/danathar/kinoite-zfs:latest
systemctl reboot
```

## Signed Switching Between Stable And Candidate

Stable channel in this project is `:latest`:

1. Stable repo: `ghcr.io/danathar/kinoite-zfs:latest`
2. Candidate repo: `ghcr.io/danathar/kinoite-zfs-candidate:<tag>`

Current images include trust policy entries for both repo names so signed
switches between these two references can work after you are already running
this image family.

If you are switching from another image family first and want strict signature
verification after that, you can either:

1. switch directly from fresh stock Kinoite (section above), or
2. do the explicit unverified bootstrap once, reboot, then switch signed.

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
