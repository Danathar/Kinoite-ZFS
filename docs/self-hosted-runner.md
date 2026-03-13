# Self-Hosted Runner

This repository uses a dedicated repo-scoped self-hosted GitHub Actions runner
for trusted jobs. The working setup documented here is for a dedicated Bluefin
VM running the runner as a Docker container.

If you are trying to make your own copy of this old BlueBuild repo work with a
Bluefin runner VM, start here. If you just want the newer project direction,
use `Danathar/zfs-kinoite-containerfile` instead.

## What Uses The Runner

The trusted akmods build jobs and the trusted BlueBuild image-build jobs in
[build.yml](../.github/workflows/build.yml) and
[build-beta.yml](../.github/workflows/build-beta.yml) target the self-hosted
label:

- `self-hosted`
- `linux`
- `x64`
- `kinoite-zfs-builder`

The PR workflow in [build-pr.yml](../.github/workflows/build-pr.yml) stays on
GitHub-hosted runners so public pull requests never execute on the VM.

## What Had To Be Done For Bluefin

This repo does more than just start a stock runner container.

1. The runner is containerized, but it uses the host Docker socket.
   The trusted workflows use GitHub Actions `container:` jobs, so the runner
   needs Docker available on the VM host to launch sibling job containers.
2. The runner binary, work directory, and tool cache live under the user's home
   directory instead of `/actions-runner`.
   Bluefin has an immutable root, and the stock runner layout can fail when
   GitHub tries to mount runner paths from `/actions-runner/...`.
3. This repo includes a local wrapper image and entrypoint under
   [`ci/github-runner/`](../ci/github-runner/) so the runner files are seeded
   into host-visible paths under `~/.local/share/kinoite-zfs-runner/`.
4. The akmods clone step applies two local-only patches to the cloned
   `Danathar/akmods` worktree before build:
   - add `--security-opt label=disable` to nested `podman build` bind mounts so
     SELinux on Bluefin does not block kernel RPM access
   - make the cloned upstream Justfile honor the configured image name from
     `images.yaml`, so this repo publishes to its own dedicated GHCR package
     names instead of the shared `akmods-zfs` namespace
5. The heavy jobs were moved to the self-hosted runner, but PR validation was
   intentionally left on GitHub-hosted runners.

That combination is what makes this Bluefin VM setup work without affecting the
other repo that also uses the akmods source fork.

## Runner Layout

- Runner image: local `kinoite-zfs-runner:local`
- Base image: `ghcr.io/myoung34/docker-github-actions-runner:ubuntu-noble`
- Repo scope: `Danathar/Kinoite-ZFS`
- Custom labels: `kinoite-zfs-builder`, `kinoite-zfs-trusted`
- Runner install dir: `~/.local/share/kinoite-zfs-runner/actions-runner`
- Persistent work dir: `~/.local/share/kinoite-zfs-runner/work`
- Tool cache dir: `~/.local/share/kinoite-zfs-runner/toolcache`

The key local files are:

- [`ci/github-runner/compose.yml`](../ci/github-runner/compose.yml)
- [`ci/github-runner/manage.sh`](../ci/github-runner/manage.sh)
- [`ci/github-runner/Dockerfile`](../ci/github-runner/Dockerfile)
- [`ci/github-runner/runner-entrypoint.sh`](../ci/github-runner/runner-entrypoint.sh)

## Prerequisites For Your Own Bluefin VM

Use a dedicated trusted VM. Do not use a general desktop or an untrusted public
build box for this workflow.

Minimum practical requirements:

- Bluefin VM
- Docker engine and `docker compose`
- GitHub CLI `gh`
- a GitHub login that can create repo runner registration tokens for the target
  repo
- this repository cloned onto the VM

On the VM used for this repo, the working commands were:

- `docker`
- `docker compose`
- `gh`
- `podman`

This VM currently has Docker from `docker-ce` and `docker-ce-cli`, the compose
plugin installed, and `gh` available from Homebrew. If your Bluefin VM differs,
the important requirement is that those commands exist and work.

## Step-By-Step Bootstrap On Bluefin

### 1. Prepare The VM

Install or provide:

- Docker engine
- Docker compose plugin
- GitHub CLI

Then verify:

```bash
docker version
docker compose version
gh --version
```

### 2. Enable Docker At Boot

This is what keeps the runner available whenever the VM is up.

```bash
sudo systemctl enable --now docker.service
systemctl is-enabled docker.service
systemctl is-active docker.service
```

The runner container itself already uses `restart: unless-stopped`, so Docker
coming up on boot is the missing piece that makes the runner return
automatically after a reboot.

### 3. Authenticate GitHub CLI

Log in with a user that can manage repository runners for the target repo.

```bash
gh auth login
gh auth status
```

### 4. Clone The Repo

```bash
git clone https://github.com/Danathar/Kinoite-ZFS.git
cd Kinoite-ZFS
```

If you are adapting this to your own fork, clone your own repo instead.

### 5. Set Repo-Specific Environment Overrides If Needed

For this repo, the defaults in [`ci/github-runner/manage.sh`](../ci/github-runner/manage.sh)
already point at `Danathar/Kinoite-ZFS`.

If you are using your own fork or your own repo, set these before bringing the
runner up:

```bash
export GITHUB_REPOSITORY=YOURUSER/YOURREPO
export REPO_URL=https://github.com/${GITHUB_REPOSITORY}
export RUNNER_NAME=kinoite-zfs-builder-$(hostname -s)
export RUNNER_LABELS=kinoite-zfs-builder,kinoite-zfs-trusted
```

If you change the labels, update the workflow `runs-on` arrays too.

### 6. Start The Runner

From the repo root on the VM:

```bash
chmod +x ci/github-runner/manage.sh
ci/github-runner/manage.sh up
```

What this does:

1. creates the persistent runner directories under
   `~/.local/share/kinoite-zfs-runner/`
2. requests a fresh repository runner registration token using `gh`
3. builds the local runner image
4. starts the `kinoite-zfs-runner` container

You should only need `up` for first bootstrap or when you intentionally want to
recreate the runner container. Do not run it on every boot.

### 7. Verify The Runner

Check the local container:

```bash
docker ps
docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}} {{.State.Status}}' kinoite-zfs-runner
```

Check the bundled status view:

```bash
ci/github-runner/manage.sh status
```

The GitHub-side runner should show as online with labels including:

- `self-hosted`
- `Linux`
- `X64`
- `kinoite-zfs-builder`

### 8. Make Trusted Workflows Use The Runner

For this repo, the heavy trusted jobs already target:

```yaml
runs-on: [self-hosted, linux, x64, kinoite-zfs-builder]
```

If you are adapting another repo, only move trusted jobs onto the self-hosted
runner. Keep public PR validation on GitHub-hosted runners unless you are fully
comfortable treating the VM as disposable and exposed.

### 9. Reboot Test

After bootstrap, verify the availability behavior explicitly:

```bash
sudo systemctl reboot
```

After the VM comes back:

```bash
systemctl is-active docker.service
docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}} {{.State.Status}}' kinoite-zfs-runner
ci/github-runner/manage.sh status
```

If Docker is active and the container restart policy is still `unless-stopped`,
the runner should reconnect on its own.

## Operational Commands

Check status:

```bash
ci/github-runner/manage.sh status
```

Follow logs:

```bash
ci/github-runner/manage.sh logs
```

Stop the container:

```bash
ci/github-runner/manage.sh stop
```

Start the existing container without re-registering:

```bash
ci/github-runner/manage.sh start
```

Remove the GitHub runner registration if you are retiring the VM:

```bash
ci/github-runner/manage.sh unregister
```

## Separation From The Other Repo

This repo now uses dedicated GHCR package names for its akmods cache:

- `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods`
- `ghcr.io/danathar/kinoite-zfs-bluebuild-akmods-candidate`

That keeps this old BlueBuild repo from reusing or overwriting the shared
`ghcr.io/danathar/akmods-zfs` cache path used by the newer container repo.

## Common Bluefin-Specific Pitfalls

1. Do not try to run this setup against an immutable-root path like
   `/actions-runner`.
   Use the bundled runner layout under `~/.local/share/kinoite-zfs-runner/`.
2. Do not remove the Docker socket mount from the runner container.
   GitHub Actions `container:` jobs need it.
3. Do not move public PR jobs onto this runner unless you are deliberately
   accepting the security risk.
4. Do not assume `manage.sh up` is the right command after every reboot.
   Once boot persistence is in place, Docker should restart the existing
   container automatically.
5. If you are adapting your own copy of this repo, read this whole document and
   confirm the target repo, runner labels, and GHCR package names before the
   first workflow run.
