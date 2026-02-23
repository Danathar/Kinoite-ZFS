# Kinoite-ZFS &nbsp; [![bluebuild build badge](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml/badge.svg)](https://github.com/Danathar/Kinoite-ZFS/actions/workflows/build.yml)

See the [BlueBuild docs](https://blue-build.org/how-to/setup/) for quick setup instructions for setting up your own repository based on this template.

After setup, it is recommended you update this README to describe your custom image.

## Installation

> [!WARNING]  
> [This is an experimental feature](https://www.fedoraproject.org/wiki/Changes/OstreeNativeContainerStable), try at your own discretion.

To rebase an existing atomic Fedora installation to the latest build:

- First rebase to the unsigned image, to get the proper signing keys and policies installed:
  ```
  rpm-ostree rebase ostree-unverified-registry:ghcr.io/danathar/kinoite-zfs:latest
  ```
- Reboot to complete the rebase:
  ```
  systemctl reboot
  ```
- Then rebase to the signed image, like so:
  ```
  rpm-ostree rebase ostree-image-signed:docker://ghcr.io/danathar/kinoite-zfs:latest
  ```
- Reboot again to complete the installation
  ```
  systemctl reboot
  ```

The `latest` tag points to the newest build we publish.

## Self-Hosted ZFS akmods

This repo builds a self-hosted `akmods-zfs` image in GHCR first, then uses those RPMs in the Kinoite image build.

- Cache image location:
  - `ghcr.io/danathar/akmods-zfs:main-<fedora>`
- Build source for cache image:
  - `ublue-os/akmods` tooling (cloned during workflow run)
- Consumer in recipe:
  - `type: containerfile` snippet in `recipes/recipe.yml`

If ZFS build or install fails, check the `Build Self-Hosted ZFS Akmods` job first in `build.yml`.

## ZFS Validation

After rebasing and rebooting, validate ZFS is available:

```bash
rpm -q kmod-zfs
modinfo zfs | head
zpool --version
zfs --version
```

For VM testing with a secondary disk attached as `/dev/vdb`:

```bash
sudo zpool create -f testpool /dev/vdb
sudo zpool status
sudo zfs create testpool/testds
sudo zfs list
```

## ISO

If build on Fedora Atomic, you can generate an offline ISO with the instructions available [here](https://blue-build.org/learn/universal-blue/#fresh-install-from-an-iso). These ISOs cannot unfortunately be distributed on GitHub for free due to large sizes, so for public projects something else has to be used for hosting.

## Verification

These images are signed with [Sigstore](https://www.sigstore.dev/)'s [cosign](https://github.com/sigstore/cosign). You can verify the signature by downloading the `cosign.pub` file from this repo and running the following command:

```bash
cosign verify --key cosign.pub ghcr.io/danathar/kinoite-zfs
```
