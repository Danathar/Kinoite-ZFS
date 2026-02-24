# Kinoite-ZFS

[![Build Main Image](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml/badge.svg)](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml)

This repository exists to test and validate ZFS support on Kinoite images built with BlueBuild.

Core goal:

- Track the current Kinoite/Fedora kernel stream.
- Build matching ZFS akmods against that kernel.
- Install those ZFS RPMs directly into the final image.
- Catch kernel/module mismatches during CI, before rebasing a host.

If you want the full technical design and workflow details, read:

- `docs/zfs-kinoite-testing.md`

That document is maintained as a living record and will be updated as each hardening issue is addressed.

## What Gets Published

- Main image:
  - `ghcr.io/danathar/kinoite-zfs:latest`
- Main akmods cache image:
  - `ghcr.io/danathar/akmods-zfs:main-<fedora>`
- Branch test image:
  - `ghcr.io/danathar/kinoite-zfs:beta-<branch>`
- Branch akmods cache image:
  - `ghcr.io/danathar/akmods-zfs-<branch>:main-<fedora>`

Branch artifacts are isolated so branch testing does not overwrite `main` artifacts.

## Workflows

- `.github/workflows/build.yml`
  - Builds and publishes `main` artifacts.
  - Runs on `main` pushes, nightly schedule, and manual dispatch.
- `.github/workflows/build-beta.yml`
  - Builds branch-tagged test artifacts for non-main branches.
  - Runs on branch pushes and manual dispatch.
- `.github/workflows/build-pr.yml`
  - PR validation build only (`push: false`, unsigned).

Markdown/docs-only changes do not trigger image builds.

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
