# Self-Hosted Runner

This repository can use a dedicated self-hosted GitHub Actions runner for trusted
build jobs. The runner is repo-scoped and labeled only for this repository, so
it does not change `Danathar/akmods` or the other container repo that also
consumes that shared akmods source.

## What Uses The Runner

Only the trusted akmods build jobs in [build.yml](../.github/workflows/build.yml)
and [build-beta.yml](../.github/workflows/build-beta.yml)
target the self-hosted label.

The PR workflow in [build-pr.yml](../.github/workflows/build-pr.yml)
stays on GitHub-hosted runners so public pull requests never execute on the VM.

## Runner Layout

- Container image: `ghcr.io/myoung34/docker-github-actions-runner:ubuntu-noble`
- Repo scope: `Danathar/Kinoite-ZFS`
- Custom labels: `kinoite-zfs-builder`, `kinoite-zfs-trusted`
- Persistent work dir: `~/.local/share/kinoite-zfs-runner/work`
- Persistent config dir: `~/.local/share/kinoite-zfs-runner/config`

The runner container mounts the host Docker socket because the trusted jobs use
GitHub Actions `container:` jobs. The work directory is mounted at the same path
inside and outside the container so sibling job containers can see the checked
out workspace.

## Bootstrap

From the repo root in the runner VM:

```bash
chmod +x ci/github-runner/manage.sh
ci/github-runner/manage.sh up
```

The script uses the current `gh` login to request a fresh repo registration
token, creates the persistent directories, and starts the container.

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

Remove the GitHub runner registration if you are retiring the VM:

```bash
ci/github-runner/manage.sh unregister
```
