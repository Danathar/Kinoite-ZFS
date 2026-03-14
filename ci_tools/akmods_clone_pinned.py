"""
Script: ci_tools/akmods_clone_pinned.py
What: Clones the exact akmods commit configured by the workflow into `/tmp/akmods`.
Doing: Recreates the directory, fetches one commit, checks detached HEAD, and verifies the SHA.
Why: Ensures we build from a known source version.
Goal: Prepare clean akmods source for later configure/build steps.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ci_tools.common import CiToolError, require_env, run_cmd


AKMODS_WORKTREE = Path("/tmp/akmods")
AKMODS_JUSTFILE = AKMODS_WORKTREE / "Justfile"


def patch_self_hosted_podman_builds() -> None:
    """
    Patch the cloned akmods Justfile for nested Podman-on-SELinux runners.

    On the Bluefin self-hosted runner, upstream `podman build` needs
    `--security-opt label=disable` when it bind-mounts the fetched kernel RPM
    cache. We patch only the local cloned worktree used by this repository so
    the shared `Danathar/akmods` source repo and other consumers stay unchanged.
    """
    original = AKMODS_JUSTFILE.read_text(encoding="utf-8")
    target = "--volume {{ KCPATH }}:/tmp/kernel_cache:ro"
    replacement = "--security-opt label=disable --volume {{ KCPATH }}:/tmp/kernel_cache:ro"
    updated = original.replace(target, replacement)

    if updated == original:
        raise CiToolError(
            "Failed to patch cloned akmods Justfile for self-hosted Podman mounts"
        )

    AKMODS_JUSTFILE.write_text(updated, encoding="utf-8")
    print("Patched cloned akmods Justfile for self-hosted Podman SELinux mounts.")


def patch_self_hosted_manifest_reuse() -> None:
    """
    Patch the cloned akmods Justfile to reuse existing local manifest names.

    The self-hosted runner keeps local Podman state between runs. Upstream
    `just manifest` creates stable manifest names such as `main-43`; on a later
    scheduled rebuild, `podman manifest create` fails if that name is already
    present locally from a previous run. We patch only this repo's temporary
    clone so repeated scheduled runs stay idempotent without changing the shared
    akmods source repo.
    """
    original = AKMODS_JUSTFILE.read_text(encoding="utf-8")
    replacements = {
        "MANIFEST=$({{ podman }} manifest create {{ manifest_image }})": (
            "MANIFEST=$({{ podman }} manifest create --replace {{ manifest_image }})"
        ),
        "MANIFEST=$({{ podman }} manifest create {{ manifest_image_kernel }})": (
            "MANIFEST=$({{ podman }} manifest create --replace {{ manifest_image_kernel }})"
        ),
    }

    updated = original
    replaced_count = 0
    for target, replacement in replacements.items():
        if target in updated:
            updated = updated.replace(target, replacement)
            replaced_count += 1

    if replaced_count != len(replacements):
        raise CiToolError(
            "Failed to patch cloned akmods Justfile for self-hosted manifest reuse"
        )

    AKMODS_JUSTFILE.write_text(updated, encoding="utf-8")
    print("Patched cloned akmods Justfile for self-hosted manifest reuse.")


def patch_repo_scoped_akmods_name() -> None:
    """
    Patch the cloned akmods Justfile to honor the configured image name.

    Upstream derives `akmods_name` only from the target type (for example
    `akmods-zfs`), which makes this repo publish into the shared package used by
    other projects. We rewrite that one line so the local clone reads the
    already-configured `images.yaml` name field instead.
    """
    original = AKMODS_JUSTFILE.read_text(encoding="utf-8")
    target = "akmods_name := 'akmods' + if akmods_target != 'common' { '-' +akmods_target } else { '' }"
    replacement = (
        "akmods_name := shell('yq \".images.$1[\\\"$2\\\"].$3.name\" images.yaml', "
        "version, kernel_flavor, akmods_target)"
    )
    updated = original.replace(target, replacement)

    if updated == original:
        raise CiToolError(
            "Failed to patch cloned akmods Justfile for repo-scoped publish names"
        )

    AKMODS_JUSTFILE.write_text(updated, encoding="utf-8")
    print("Patched cloned akmods Justfile to honor repo-scoped image names.")


def main() -> None:
    # Workflow inputs that define exactly which akmods source to use.
    upstream_repo = require_env("AKMODS_UPSTREAM_REPO")
    upstream_ref = require_env("AKMODS_UPSTREAM_REF")

    # Start from a clean checkout each run so there is no leftover state.
    shutil.rmtree(AKMODS_WORKTREE, ignore_errors=True)
    AKMODS_WORKTREE.mkdir(parents=True, exist_ok=True)

    # Create a minimal local repository at /tmp/akmods.
    # We intentionally fetch only one commit so this stays fast and deterministic.
    run_cmd(["git", "init", "."], cwd=str(AKMODS_WORKTREE))
    run_cmd(["git", "remote", "add", "origin", upstream_repo], cwd=str(AKMODS_WORKTREE))
    run_cmd(["git", "fetch", "--depth", "1", "origin", upstream_ref], cwd=str(AKMODS_WORKTREE))

    # Detached checkout keeps this worktree pinned to one exact commit (not a branch tip).
    run_cmd(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=str(AKMODS_WORKTREE))

    # Defense-in-depth: fail if Git resolved to anything other than the expected SHA.
    resolved_ref = run_cmd(["git", "rev-parse", "HEAD"], cwd=str(AKMODS_WORKTREE)).strip()
    if resolved_ref != upstream_ref:
        raise CiToolError(f"Pinned ref mismatch: expected {upstream_ref}, got {resolved_ref}")

    patch_self_hosted_podman_builds()
    patch_self_hosted_manifest_reuse()
    patch_repo_scoped_akmods_name()
    print(f"Using pinned akmods ref: {resolved_ref}")


if __name__ == "__main__":
    main()
