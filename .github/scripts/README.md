# Workflow Script Layout

These scripts hold CI shell logic that was previously embedded inline in workflow YAML.

Goal:

- Keep workflow files orchestration-focused (`on`, `needs`, `if`, permissions, action wiring).
- Keep shell behavior versioned, testable, and easier to review in focused files.

## Main Pipeline Scripts

- `main/resolve-build-inputs.sh`: Resolve lock/default build inputs and emit outputs.
- `main/write-build-inputs-manifest.sh`: Emit `artifacts/build-inputs.json` for replay/audit.
- `main/check-candidate-akmods-cache.sh`: Detect usable candidate/stable akmods cache.
- `main/configure-candidate-recipe.sh`: Rewrite `recipes/recipe.yml` for candidate build inputs.
- `main/promote-stable.sh`: Promote candidate outputs to stable/audit tags.

## Branch Pipeline Scripts

- `beta/compute-branch-metadata.sh`: Generate branch-safe image and akmods names.
- `beta/detect-fedora-version.sh`: Resolve Fedora major and kernel release for branch build.
- `beta/check-branch-akmods-cache.sh`: Detect branch cache suitability by exact kernel match.
- `beta/configure-branch-recipe.sh`: Rewrite `recipes/recipe.yml` for branch image/tag inputs.

## Shared Akmods Scripts

- `akmods/clone-pinned-akmods.sh`: Clone and verify pinned akmods source commit.
- `akmods/configure-zfs-target.sh`: Add/update zfs target in `images.yaml`.
- `akmods/build-and-publish.sh`: Execute `just` build/publish/manifest flow.

Containerfile note:

- `AKMODS_IMAGE` is now defined in `containerfiles/zfs-akmods/Containerfile`.
- Main/branch recipe-configuration scripts rewrite that line in the Containerfile,
  while `image-version` and `base-image` remain in `recipes/recipe.yml`.

## Usage Notes

- Scripts assume required values are passed through workflow `env`.
- GitHub expressions (`${{ ... }}`) are resolved in workflow YAML, not in scripts.
- Outputs must still be written through `GITHUB_OUTPUT` when a step uses `id` outputs.
