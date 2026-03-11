"""
Script: tests/test_beta_configure_branch_recipe.py
What: Tests for branch/PR recipe shaping.
Doing: Generates a temporary BlueBuild workspace for branch/PR runs and checks the final values.
Why: Protects the phase-2 change that moved non-main build edits into generated files.
Goal: Keep branch and PR validation honest about which base image and akmods tag they use.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from ci_tools import beta_configure_branch_recipe
import ci_tools.generated_build_context as generated_build_context


class BetaConfigureBranchRecipeTests(unittest.TestCase):
    def test_pins_base_image_and_branch_scoped_akmods_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_file = root / "recipes" / "recipe.yml"
            containerfile = root / "containerfiles" / "zfs-akmods" / "Containerfile"
            files_dir = root / "files" / "scripts"
            generated_root = root / ".generated" / "bluebuild"

            recipe_file.parent.mkdir(parents=True, exist_ok=True)
            containerfile.parent.mkdir(parents=True, exist_ok=True)
            files_dir.mkdir(parents=True, exist_ok=True)
            recipe_file.write_text(
                "\n".join(
                    [
                        "name: kinoite-zfs",
                        "base-image: ghcr.io/ublue-os/kinoite-main",
                        "image-version: latest",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            containerfile.write_text(
                'AKMODS_IMAGE="ghcr.io/example/akmods-zfs:main-${FEDORA_VERSION}"\n',
                encoding="utf-8",
            )
            (files_dir / "ensure-repo-signing-policy.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            (root / "cosign.pub").write_text("public-key\n", encoding="utf-8")

            env = {
                "GITHUB_REPOSITORY_OWNER": "Danathar",
                "AKMODS_REPO": "akmods-zfs-candidate",
                "AKMODS_TAG_PREFIX": "br-feature-test",
                "BASE_IMAGE_NAME": "ghcr.io/ublue-os/kinoite-main",
                "BASE_IMAGE_TAG": "latest-20260307.1",
            }
            with (
                mock.patch.object(generated_build_context, "CANONICAL_RECIPE_FILE", recipe_file),
                mock.patch.object(generated_build_context, "CANONICAL_CONTAINERFILE", containerfile),
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
                mock.patch.dict(os.environ, env, clear=False),
            ):
                beta_configure_branch_recipe.main()

            generated_recipe = generated_root / "recipes" / "recipe.yml"
            generated_containerfile = generated_root / "containerfiles" / "zfs-akmods" / "Containerfile"
            self.assertIn(
                "base-image: ghcr.io/ublue-os/kinoite-main\n",
                generated_recipe.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "image-version: latest-20260307.1\n",
                generated_recipe.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                generated_containerfile.read_text(encoding="utf-8"),
                'AKMODS_IMAGE="ghcr.io/danathar/akmods-zfs-candidate:br-feature-test-${FEDORA_VERSION}"\n',
            )
            self.assertIn("image-version: latest\n", recipe_file.read_text(encoding="utf-8"))

    def test_defaults_to_main_tag_prefix_when_not_provided(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_file = root / "recipes" / "recipe.yml"
            containerfile = root / "containerfiles" / "zfs-akmods" / "Containerfile"
            files_dir = root / "files" / "scripts"
            generated_root = root / ".generated" / "bluebuild"

            recipe_file.parent.mkdir(parents=True, exist_ok=True)
            containerfile.parent.mkdir(parents=True, exist_ok=True)
            files_dir.mkdir(parents=True, exist_ok=True)
            recipe_file.write_text(
                "name: kinoite-zfs\nbase-image: old\nimage-version: old\n",
                encoding="utf-8",
            )
            containerfile.write_text('AKMODS_IMAGE="old"\n', encoding="utf-8")
            (files_dir / "ensure-repo-signing-policy.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            (root / "cosign.pub").write_text("public-key\n", encoding="utf-8")

            env = {
                "GITHUB_REPOSITORY_OWNER": "Danathar",
                "AKMODS_REPO": "akmods-zfs",
                "BASE_IMAGE_NAME": "ghcr.io/ublue-os/kinoite-main",
                "BASE_IMAGE_TAG": "43-20260307.1",
            }
            with (
                mock.patch.object(generated_build_context, "CANONICAL_RECIPE_FILE", recipe_file),
                mock.patch.object(generated_build_context, "CANONICAL_CONTAINERFILE", containerfile),
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
                mock.patch.dict(os.environ, env, clear=False),
            ):
                beta_configure_branch_recipe.main()

            self.assertEqual(
                (generated_root / "containerfiles" / "zfs-akmods" / "Containerfile").read_text(
                    encoding="utf-8"
                ),
                'AKMODS_IMAGE="ghcr.io/danathar/akmods-zfs:main-${FEDORA_VERSION}"\n',
            )


if __name__ == "__main__":
    unittest.main()
