# Kinoite-ZFS Glossary

This page defines terms used across this repository's docs and workflow comments.

## Core Terms

- `CI`: the GitHub Actions workflows in `.github/workflows`.
- `candidate`: test image/tag built first.
- `stable`: user-facing tags (`latest` and `main-<fedora>`).
- `branch-scoped`: a tag/name that includes the branch identifier (for example `br-my-branch-43`) so branch test artifacts stay isolated.
- `metadata`: descriptive data attached to an object (for example image labels or workflow run details).
- `artifact`: a file/package/output saved by a workflow run so you can inspect or reuse it later.
- `manifest`: a structured data file that records what a run produced or which exact inputs it used.
- `workflow`: one named GitHub Actions automation file (for example `build.yml`) that defines jobs and steps.
- `workflow metadata`: run details like run ID, run number, branch/ref, commit SHA, and triggering user.
- `workflow run`: one execution of a GitHub Actions workflow from start to finish (one run has its own run ID and logs).
- `pipeline`: the ordered set of jobs/steps in a workflow run (for example: resolve inputs -> build candidate -> promote stable).
- `compose` / `compose step`: the image build step that combines the base image + configured modules/packages into the final publishable image.
- `package visibility` (registry): who can read a container package/tag. This is separate from source repo visibility, so a public code repo can still have package paths that require auth.
- `build-inputs` artifact: JSON file saved per run with the exact inputs that run used.
- `Fedora stream` / `kernel stream`: the ongoing flow of new kernel releases in Fedora over time (for example one nightly run may see a newer kernel than yesterday).
- `tag`: a human-readable label on an image, like `latest` or `main-43`.
- `image ref`: text that points to a container image, usually `name:tag` or `name@sha256:digest`.
- `digest`: an immutable hash that identifies one exact image content snapshot.
- `namespace` (registry namespace): the owner/org part of an image path, for example `danathar` in `ghcr.io/danathar/kinoite-zfs`.
- `rebase` / `rebasing` (rpm-ostree): switching your installed OS image source to a different container image ref/tag.
- `floating ref` / `floating latest ref`: a tag-based ref (for example `:latest`) that can point to a different image later without changing its text.
- `digest-pinned ref`: an exact image pointer like `name@sha256:...`; this does not move to a different image unless you change the digest value.
- `tag vs digest-pinned` (plain language): a tag is a moving signpost, while a digest is an exact snapshot.
- `signature` (image signature): cryptographic proof that an image digest was signed by a trusted key.
- `fail closed`: if a required safety input is missing, stop with an error instead of guessing or silently reusing old data.
- `stale module` / `stale kmod`: a kernel module built for an older kernel release than the one currently in the base image.
- `harden` / `hardening`: add safety checks or stricter rules so failures are less likely and easier to catch early.
- `SHA` / `commit SHA`: the hash that identifies one exact Git commit.
- `PR` (pull request): a proposed branch change reviewed before merging into the target branch.
- `VM` (virtual machine): a software-defined computer used for testing without touching a physical host install.
- `OCI`: Open Container Initiative standards used for container image formats and registries.
- `YAML`: a human-readable config file format used by GitHub Actions workflow files.

## Command Glossary

- `gh`: GitHub CLI. Used to list runs, inspect jobs, and download run files.
- `skopeo`: reads/copies container images without running them.
- `jq`: reads and filters JSON output.
- `JSON`: structured text format used for machine-readable data and workflow artifacts.
- `rpm-ostree`: manages package layering/rebase on atomic Fedora systems (like Kinoite).
- `cosign`: verifies container image signatures.
