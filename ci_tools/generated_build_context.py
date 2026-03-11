"""
Script: ci_tools/generated_build_context.py
What: Creates a generated BlueBuild workspace for one workflow job.
Doing: Copies the local files BlueBuild needs into a transient directory and writes run-specific values there.
Why: CI should not mutate checked-in recipe/containerfile source files in place.
Goal: Keep canonical repo files stable while still allowing per-run base/akmods pinning.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from ci_tools.common import CiToolError, print_lines_starting_with, replace_line_starting_with


# Canonical source files tracked in git.
CANONICAL_RECIPE_FILE = Path("recipes/recipe.yml")
CANONICAL_CONTAINERFILE = Path("containerfiles/zfs-akmods/Containerfile")
CANONICAL_FILES_DIR = Path("files")
CANONICAL_MODULES_DIR = Path("modules")
CANONICAL_COSIGN_PUB = Path("cosign.pub")

# Generated workspace used only inside one job workspace.
# "Generated workspace" here means a transient directory created during CI that
# BlueBuild treats as its working tree for the current run. It is safe to delete.
GENERATED_WORKSPACE_DIR = Path(".generated/bluebuild")
GENERATED_RECIPE_FILE = GENERATED_WORKSPACE_DIR / "recipes" / "recipe.yml"
GENERATED_CONTAINERFILE = GENERATED_WORKSPACE_DIR / "containerfiles" / "zfs-akmods" / "Containerfile"
GENERATED_FILES_DIR = GENERATED_WORKSPACE_DIR / "files"
GENERATED_MODULES_DIR = GENERATED_WORKSPACE_DIR / "modules"
GENERATED_COSIGN_PUB = GENERATED_WORKSPACE_DIR / "cosign.pub"


@dataclass(frozen=True)
class BuildContextConfig:
    """
    Run-specific values used to shape the generated BlueBuild workspace.

    `image_name` is optional because branch/PR validation keeps the canonical
    image name, while candidate builds intentionally switch to the dedicated
    candidate repository name before promotion.
    """

    base_image_name: str
    base_image_tag: str
    akmods_image: str
    image_name: str | None = None


def generated_working_directory() -> str:
    """
    Return the transient working directory path used by BlueBuild.

    The GitHub action's `working_directory` input points here so the build reads
    generated copies instead of the checked-in repo files.
    """

    return str(GENERATED_WORKSPACE_DIR)


def _require_path(path: Path, *, kind: str) -> None:
    """Fail clearly when a required canonical file/directory is missing."""
    if not path.exists():
        raise CiToolError(f"Missing required {kind}: {path}")


def _copy_tree(source: Path, destination: Path) -> None:
    """
    Copy one local directory into the generated workspace.

    We remove the old generated tree first so stale files from a previous job
    cannot leak into the current build context.
    """

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def prepare_generated_build_context(config: BuildContextConfig) -> None:
    """
    Create a fresh generated BlueBuild workspace and apply run-specific values.

    Why copy a small workspace instead of editing files in place:
    1. The canonical repo files stay unchanged for later steps and reviewers.
    2. Logs can still show the exact effective values used by this run.
    3. Retry steps can rebuild from the same generated inputs without re-editing
       tracked source files.
    """

    _require_path(CANONICAL_RECIPE_FILE, kind="recipe file")
    _require_path(CANONICAL_CONTAINERFILE, kind="containerfile")
    _require_path(CANONICAL_FILES_DIR, kind="files directory")
    _require_path(CANONICAL_COSIGN_PUB, kind="public signing key")

    if GENERATED_WORKSPACE_DIR.exists():
        shutil.rmtree(GENERATED_WORKSPACE_DIR)

    GENERATED_RECIPE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_CONTAINERFILE.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(CANONICAL_RECIPE_FILE, GENERATED_RECIPE_FILE)
    shutil.copy2(CANONICAL_CONTAINERFILE, GENERATED_CONTAINERFILE)
    _copy_tree(CANONICAL_FILES_DIR, GENERATED_FILES_DIR)
    shutil.copy2(CANONICAL_COSIGN_PUB, GENERATED_COSIGN_PUB)

    # Local `modules/` is optional today, but copying it when present keeps the
    # generated workspace ready for future local-module additions.
    if CANONICAL_MODULES_DIR.exists():
        _copy_tree(CANONICAL_MODULES_DIR, GENERATED_MODULES_DIR)

    if config.image_name is not None:
        replace_line_starting_with(GENERATED_RECIPE_FILE, "name:", f"name: {config.image_name}")

    replace_line_starting_with(
        GENERATED_RECIPE_FILE,
        "base-image:",
        f"base-image: {config.base_image_name}",
    )
    replace_line_starting_with(
        GENERATED_RECIPE_FILE,
        "image-version:",
        f"image-version: {config.base_image_tag}",
    )
    replace_line_starting_with(
        GENERATED_CONTAINERFILE,
        "AKMODS_IMAGE=",
        f'AKMODS_IMAGE="{config.akmods_image}"',
    )

    print(f"Generated build workspace: {GENERATED_WORKSPACE_DIR}")
    print_lines_starting_with(GENERATED_RECIPE_FILE, "name:")
    print_lines_starting_with(GENERATED_RECIPE_FILE, "base-image:")
    print_lines_starting_with(GENERATED_RECIPE_FILE, "image-version:")
    print_lines_starting_with(GENERATED_CONTAINERFILE, "AKMODS_IMAGE=")
