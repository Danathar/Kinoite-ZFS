"""
Script: tests/test_akmods_clone_pinned.py
What: Tests for the pinned akmods clone helper's local Justfile patching.
Doing: Verifies the self-hosted runner workaround rewrites nested Podman bind mounts and fails loudly if upstream changes shape.
Why: The workaround must stay local to this repo and remain easy to validate when the pinned akmods source changes.
Goal: Prevent regressions in the self-hosted SELinux mount fix without touching the shared akmods repo.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ci_tools.akmods_clone_pinned import (
    patch_repo_scoped_akmods_name,
    patch_self_hosted_podman_builds,
)
from ci_tools.common import CiToolError


class AkmodsClonePinnedTests(unittest.TestCase):
    def test_patch_self_hosted_podman_builds_rewrites_nested_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            justfile = Path(temp_dir) / "Justfile"
            justfile.write_text(
                "\n".join(
                    [
                        "podman build -f Containerfile.in --volume {{ KCPATH }}:/tmp/kernel_cache:ro --target RPMS /tmp/akmods",
                        "podman build -f Containerfile.test --volume {{ KCPATH }}:/tmp/kernel_cache:ro /tmp/akmods",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("ci_tools.akmods_clone_pinned.AKMODS_JUSTFILE", justfile):
                patch_self_hosted_podman_builds()

            updated = justfile.read_text(encoding="utf-8")
            self.assertEqual(updated.count("--security-opt label=disable"), 2)
            self.assertNotIn("--volume {{ KCPATH }}:/tmp/kernel_cache:ro", updated.replace(
                "--security-opt label=disable --volume {{ KCPATH }}:/tmp/kernel_cache:ro",
                "",
            ))

    def test_patch_self_hosted_podman_builds_fails_when_upstream_shape_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            justfile = Path(temp_dir) / "Justfile"
            justfile.write_text("podman build -f Containerfile.in /tmp/akmods\n", encoding="utf-8")

            with patch("ci_tools.akmods_clone_pinned.AKMODS_JUSTFILE", justfile):
                with self.assertRaisesRegex(
                    CiToolError,
                    "Failed to patch cloned akmods Justfile",
                ):
                    patch_self_hosted_podman_builds()

    def test_patch_repo_scoped_akmods_name_uses_images_yaml_name_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            justfile = Path(temp_dir) / "Justfile"
            justfile.write_text(
                "akmods_name := 'akmods' + if akmods_target != 'common' { '-' +akmods_target } else { '' }\n",
                encoding="utf-8",
            )

            with patch("ci_tools.akmods_clone_pinned.AKMODS_JUSTFILE", justfile):
                patch_repo_scoped_akmods_name()

            updated = justfile.read_text(encoding="utf-8")
            self.assertIn('.images.$1[\\"$2\\"].$3.name', updated)
            self.assertNotIn("akmods_name := 'akmods' + if akmods_target != 'common'", updated)

    def test_patch_repo_scoped_akmods_name_fails_when_upstream_shape_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            justfile = Path(temp_dir) / "Justfile"
            justfile.write_text("akmods_name := env('AKMODS_NAME', 'custom')\n", encoding="utf-8")

            with patch("ci_tools.akmods_clone_pinned.AKMODS_JUSTFILE", justfile):
                with self.assertRaisesRegex(
                    CiToolError,
                    "Failed to patch cloned akmods Justfile for repo-scoped publish names",
                ):
                    patch_repo_scoped_akmods_name()


if __name__ == "__main__":
    unittest.main()
