"""
Script: tests/test_configure_generated_build_context.py
What: Tests for the shared generated-build-context command.
Doing: Supplies workflow-like environment values and checks the generated workspace output for candidate and branch-style cases.
Why: Protects the simplification that replaced two near-identical wrapper commands with one shared command.
Goal: Keep main, branch, and PR build-context generation behavior identical after command unification.
"""

from __future__ import annotations

from contextlib import ExitStack
import os
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from ci_tools import configure_generated_build_context
import ci_tools.generated_build_context as generated_build_context


def _patch_generated_paths(root: Path):
    generated_root = root / ".generated" / "bluebuild"
    return (
        mock.patch.object(generated_build_context, "CANONICAL_RECIPE_FILE", root / "recipes" / "recipe.yml"),
        mock.patch.object(
            generated_build_context,
            "CANONICAL_CONTAINERFILE",
            root / "containerfiles" / "zfs-akmods" / "Containerfile",
        ),
        mock.patch.object(generated_build_context, "CANONICAL_FILES_DIR", root / "files"),
        mock.patch.object(generated_build_context, "CANONICAL_MODULES_DIR", root / "modules"),
        mock.patch.object(generated_build_context, "CANONICAL_COSIGN_PUB", root / "cosign.pub"),
        mock.patch.object(generated_build_context, "GENERATED_WORKSPACE_DIR", generated_root),
        mock.patch.object(generated_build_context, "GENERATED_RECIPE_FILE", generated_root / "recipes" / "recipe.yml"),
        mock.patch.object(
            generated_build_context,
            "GENERATED_CONTAINERFILE",
            generated_root / "containerfiles" / "zfs-akmods" / "Containerfile",
        ),
        mock.patch.object(generated_build_context, "GENERATED_FILES_DIR", generated_root / "files"),
        mock.patch.object(generated_build_context, "GENERATED_MODULES_DIR", generated_root / "modules"),
        mock.patch.object(generated_build_context, "GENERATED_COSIGN_PUB", generated_root / "cosign.pub"),
    )


class ConfigureGeneratedBuildContextTests(unittest.TestCase):
    def _write_canonical_inputs(self, root: Path) -> None:
        (root / "recipes").mkdir(parents=True, exist_ok=True)
        (root / "containerfiles" / "zfs-akmods").mkdir(parents=True, exist_ok=True)
        (root / "files" / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "modules").mkdir(parents=True, exist_ok=True)
        (root / "recipes" / "recipe.yml").write_text(
            "name: kinoite-zfs\nbase-image: ghcr.io/ublue-os/kinoite-main\nimage-version: latest\n",
            encoding="utf-8",
        )
        (root / "containerfiles" / "zfs-akmods" / "Containerfile").write_text(
            'AKMODS_IMAGE="ghcr.io/example/akmods-zfs:main-${FEDORA_VERSION}"\n',
            encoding="utf-8",
        )
        (root / "files" / "scripts" / "ensure-repo-signing-policy.sh").write_text(
            "#!/bin/bash\nexit 0\n",
            encoding="utf-8",
        )
        (root / "modules" / ".gitkeep").write_text("", encoding="utf-8")
        (root / "cosign.pub").write_text("public-key\n", encoding="utf-8")

    def test_generates_candidate_context_when_image_name_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_canonical_inputs(root)

            env = {
                "GITHUB_REPOSITORY_OWNER": "Danathar",
                "IMAGE_NAME": "kinoite-zfs-candidate",
                "AKMODS_REPO": "akmods-zfs-candidate",
                "BASE_IMAGE_NAME": "ghcr.io/ublue-os/kinoite-main",
                "BASE_IMAGE_TAG": "latest-20260311.1",
            }
            with ExitStack() as stack:
                for patcher in _patch_generated_paths(root):
                    stack.enter_context(patcher)
                stack.enter_context(mock.patch.dict(os.environ, env, clear=False))
                configure_generated_build_context.main()

            generated_recipe = (root / ".generated" / "bluebuild" / "recipes" / "recipe.yml").read_text(
                encoding="utf-8"
            )
            generated_containerfile = (
                root / ".generated" / "bluebuild" / "containerfiles" / "zfs-akmods" / "Containerfile"
            ).read_text(encoding="utf-8")

            self.assertIn("name: kinoite-zfs-candidate\n", generated_recipe)
            self.assertIn("image-version: latest-20260311.1\n", generated_recipe)
            self.assertEqual(
                generated_containerfile,
                'AKMODS_IMAGE="ghcr.io/danathar/akmods-zfs-candidate:main-${FEDORA_VERSION}"\n',
            )

    def test_generates_branch_context_when_branch_tag_prefix_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_canonical_inputs(root)

            env = {
                "GITHUB_REPOSITORY_OWNER": "Danathar",
                "AKMODS_REPO": "akmods-zfs-candidate",
                "AKMODS_TAG_PREFIX": "br-feature-test",
                "BASE_IMAGE_NAME": "ghcr.io/ublue-os/kinoite-main",
                "BASE_IMAGE_TAG": "43-20260311.1",
            }
            with ExitStack() as stack:
                for patcher in _patch_generated_paths(root):
                    stack.enter_context(patcher)
                stack.enter_context(mock.patch.dict(os.environ, env, clear=False))
                configure_generated_build_context.main()

            generated_recipe = (root / ".generated" / "bluebuild" / "recipes" / "recipe.yml").read_text(
                encoding="utf-8"
            )
            generated_containerfile = (
                root / ".generated" / "bluebuild" / "containerfiles" / "zfs-akmods" / "Containerfile"
            ).read_text(encoding="utf-8")

            self.assertIn("name: kinoite-zfs\n", generated_recipe)
            self.assertIn("image-version: 43-20260311.1\n", generated_recipe)
            self.assertEqual(
                generated_containerfile,
                'AKMODS_IMAGE="ghcr.io/danathar/akmods-zfs-candidate:br-feature-test-${FEDORA_VERSION}"\n',
            )

    def test_defaults_to_main_prefix_when_wrapper_passes_empty_tag_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_canonical_inputs(root)

            env = {
                "GITHUB_REPOSITORY_OWNER": "Danathar",
                "IMAGE_NAME": "kinoite-zfs-candidate",
                "AKMODS_REPO": "akmods-zfs-candidate",
                # Composite actions can pass an empty optional input as an empty
                # env var. This must still behave like the historical main-flow
                # default, not produce `:-${FEDORA_VERSION}`.
                "AKMODS_TAG_PREFIX": "",
                "BASE_IMAGE_NAME": "ghcr.io/ublue-os/kinoite-main",
                "BASE_IMAGE_TAG": "latest-20260311.1",
            }
            with ExitStack() as stack:
                for patcher in _patch_generated_paths(root):
                    stack.enter_context(patcher)
                stack.enter_context(mock.patch.dict(os.environ, env, clear=False))
                configure_generated_build_context.main()

            generated_containerfile = (
                root / ".generated" / "bluebuild" / "containerfiles" / "zfs-akmods" / "Containerfile"
            ).read_text(encoding="utf-8")

            self.assertEqual(
                generated_containerfile,
                'AKMODS_IMAGE="ghcr.io/danathar/akmods-zfs-candidate:main-${FEDORA_VERSION}"\n',
            )


if __name__ == "__main__":
    unittest.main()
