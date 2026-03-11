"""
Script: tests/test_generated_build_context.py
What: Tests for generated BlueBuild workspace preparation.
Doing: Builds temporary canonical inputs, generates a transient workspace, and checks the output files.
Why: Protects the phase-2 change that stops CI from mutating checked-in files in place.
Goal: Keep generated build inputs correct while preserving canonical source files unchanged.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest import mock

from ci_tools.generated_build_context import BuildContextConfig, prepare_generated_build_context
import ci_tools.generated_build_context as generated_build_context


class GeneratedBuildContextTests(unittest.TestCase):
    def test_generates_transient_workspace_without_mutating_canonical_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            canonical_recipe = root / "recipes" / "recipe.yml"
            canonical_containerfile = root / "containerfiles" / "zfs-akmods" / "Containerfile"
            canonical_helper = (
                root / "containerfiles" / "zfs-akmods" / "install_zfs_from_akmods_cache.py"
            )
            canonical_files_dir = root / "files" / "scripts"
            canonical_modules_dir = root / "modules"
            canonical_cosign_pub = root / "cosign.pub"
            generated_root = root / ".generated" / "bluebuild"

            canonical_recipe.parent.mkdir(parents=True, exist_ok=True)
            canonical_containerfile.parent.mkdir(parents=True, exist_ok=True)
            canonical_files_dir.mkdir(parents=True, exist_ok=True)
            canonical_modules_dir.mkdir(parents=True, exist_ok=True)

            canonical_recipe.write_text(
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
            canonical_containerfile.write_text(
                'ENV AKMODS_IMAGE_TEMPLATE="ghcr.io/example/akmods-zfs:main-{fedora}"\n',
                encoding="utf-8",
            )
            canonical_helper.write_text(
                "#!/usr/bin/env python3\nprint('helper')\n",
                encoding="utf-8",
            )
            (canonical_files_dir / "ensure-repo-signing-policy.sh").write_text(
                "#!/bin/bash\nexit 0\n",
                encoding="utf-8",
            )
            (canonical_modules_dir / ".gitkeep").write_text("", encoding="utf-8")
            canonical_cosign_pub.write_text("public-key\n", encoding="utf-8")

            with (
                mock.patch.object(generated_build_context, "CANONICAL_RECIPE_FILE", canonical_recipe),
                mock.patch.object(
                    generated_build_context,
                    "CANONICAL_CONTAINERFILE",
                    canonical_containerfile,
                ),
                mock.patch.object(
                    generated_build_context,
                    "CANONICAL_FILES_DIR",
                    root / "files",
                ),
                mock.patch.object(
                    generated_build_context,
                    "CANONICAL_MODULES_DIR",
                    canonical_modules_dir,
                ),
                mock.patch.object(
                    generated_build_context,
                    "CANONICAL_COSIGN_PUB",
                    canonical_cosign_pub,
                ),
                mock.patch.object(
                    generated_build_context,
                    "GENERATED_WORKSPACE_DIR",
                    generated_root,
                ),
                mock.patch.object(
                    generated_build_context,
                    "GENERATED_RECIPE_FILE",
                    generated_root / "recipes" / "recipe.yml",
                ),
                mock.patch.object(
                    generated_build_context,
                    "GENERATED_CONTAINERFILE",
                    generated_root / "containerfiles" / "zfs-akmods" / "Containerfile",
                ),
                mock.patch.object(
                    generated_build_context,
                    "GENERATED_FILES_DIR",
                    generated_root / "files",
                ),
                mock.patch.object(
                    generated_build_context,
                    "GENERATED_MODULES_DIR",
                    generated_root / "modules",
                ),
                mock.patch.object(
                    generated_build_context,
                    "GENERATED_COSIGN_PUB",
                    generated_root / "cosign.pub",
                ),
            ):
                prepare_generated_build_context(
                    BuildContextConfig(
                        image_name="kinoite-zfs-candidate",
                        base_image_name="ghcr.io/ublue-os/kinoite-main",
                        base_image_tag="latest-20260311.1",
                        akmods_image_template="ghcr.io/danathar/akmods-zfs-candidate:main-{fedora}",
                    )
                )

            # Canonical inputs stay unchanged.
            self.assertIn("name: kinoite-zfs\n", canonical_recipe.read_text(encoding="utf-8"))
            self.assertIn(
                "image-version: latest\n",
                canonical_recipe.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                canonical_containerfile.read_text(encoding="utf-8"),
                'ENV AKMODS_IMAGE_TEMPLATE="ghcr.io/example/akmods-zfs:main-{fedora}"\n',
            )

            # Generated outputs carry the run-specific values instead.
            generated_recipe_text = (
                generated_root / "recipes" / "recipe.yml"
            ).read_text(encoding="utf-8")
            generated_containerfile_text = (
                generated_root / "containerfiles" / "zfs-akmods" / "Containerfile"
            ).read_text(encoding="utf-8")
            self.assertIn("name: kinoite-zfs-candidate\n", generated_recipe_text)
            self.assertIn(
                "base-image: ghcr.io/ublue-os/kinoite-main\n",
                generated_recipe_text,
            )
            self.assertIn("image-version: latest-20260311.1\n", generated_recipe_text)
            self.assertEqual(
                generated_containerfile_text,
                'ENV AKMODS_IMAGE_TEMPLATE="ghcr.io/danathar/akmods-zfs-candidate:main-{fedora}"\n',
            )

            # Files BlueBuild needs at build time are present in the generated workspace.
            self.assertTrue((generated_root / "files" / "scripts" / "ensure-repo-signing-policy.sh").exists())
            self.assertTrue((generated_root / "modules" / ".gitkeep").exists())
            self.assertTrue((generated_root / "cosign.pub").exists())
            self.assertTrue(
                (
                    generated_root
                    / "containerfiles"
                    / "zfs-akmods"
                    / "install_zfs_from_akmods_cache.py"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
