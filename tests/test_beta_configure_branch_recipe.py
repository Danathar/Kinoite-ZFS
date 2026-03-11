"""
Script: tests/test_beta_configure_branch_recipe.py
What: Tests for branch/PR recipe shaping.
Doing: Rewrites temporary recipe/containerfile fixtures and checks the final values.
Why: Protects the phase-1 change that pins non-main validation to resolved `main` inputs.
Goal: Keep branch and PR validation honest about which base image and akmods tag they use.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from ci_tools import beta_configure_branch_recipe


class BetaConfigureBranchRecipeTests(unittest.TestCase):
    def test_pins_base_image_and_branch_scoped_akmods_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_file = root / "recipe.yml"
            containerfile = root / "Containerfile"

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

            env = {
                "GITHUB_REPOSITORY_OWNER": "Danathar",
                "AKMODS_REPO": "akmods-zfs-candidate",
                "AKMODS_TAG_PREFIX": "br-feature-test",
                "BASE_IMAGE_NAME": "ghcr.io/ublue-os/kinoite-main",
                "BASE_IMAGE_TAG": "latest-20260307.1",
            }
            with (
                mock.patch.object(beta_configure_branch_recipe, "RECIPE_FILE", recipe_file),
                mock.patch.object(beta_configure_branch_recipe, "ZFS_CONTAINERFILE", containerfile),
                mock.patch.dict(os.environ, env, clear=False),
            ):
                beta_configure_branch_recipe.main()

            self.assertIn(
                "base-image: ghcr.io/ublue-os/kinoite-main\n",
                recipe_file.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "image-version: latest-20260307.1\n",
                recipe_file.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                containerfile.read_text(encoding="utf-8"),
                'AKMODS_IMAGE="ghcr.io/danathar/akmods-zfs-candidate:br-feature-test-${FEDORA_VERSION}"\n',
            )

    def test_defaults_to_main_tag_prefix_when_not_provided(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_file = root / "recipe.yml"
            containerfile = root / "Containerfile"

            recipe_file.write_text(
                "base-image: old\nimage-version: old\n",
                encoding="utf-8",
            )
            containerfile.write_text('AKMODS_IMAGE="old"\n', encoding="utf-8")

            env = {
                "GITHUB_REPOSITORY_OWNER": "Danathar",
                "AKMODS_REPO": "akmods-zfs",
                "BASE_IMAGE_NAME": "ghcr.io/ublue-os/kinoite-main",
                "BASE_IMAGE_TAG": "43-20260307.1",
            }
            with (
                mock.patch.object(beta_configure_branch_recipe, "RECIPE_FILE", recipe_file),
                mock.patch.object(beta_configure_branch_recipe, "ZFS_CONTAINERFILE", containerfile),
                mock.patch.dict(os.environ, env, clear=False),
            ):
                beta_configure_branch_recipe.main()

            self.assertEqual(
                containerfile.read_text(encoding="utf-8"),
                'AKMODS_IMAGE="ghcr.io/danathar/akmods-zfs:main-${FEDORA_VERSION}"\n',
            )


if __name__ == "__main__":
    unittest.main()
