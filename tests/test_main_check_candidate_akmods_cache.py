"""
Script: tests/test_main_check_candidate_akmods_cache.py
What: Tests for main akmods cache validation helpers.
Doing: Creates temporary RPM trees and checks missing-kernel detection.
Why: Protects the multi-kernel cache check added for base images with fallback kernels.
Goal: Keep rebuild decisions fail-closed when any required kernel RPM is absent.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from ci_tools.main_check_candidate_akmods_cache import (
    _missing_kernel_releases,
    AkmodsCacheStatus,
    inspect_candidate_akmods_cache,
    write_cache_status_outputs,
)


class MainCheckCandidateAkmodsCacheTests(unittest.TestCase):
    def test_reports_missing_kernel_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rpm_dir = root / "rpms" / "kmods" / "zfs"
            rpm_dir.mkdir(parents=True, exist_ok=True)

            # This file name follows the cache-check glob pattern used by the workflow.
            (rpm_dir / "kmod-zfs-6.18.13-200.fc43.x86_64-2.4.1-1.fc43.x86_64.rpm").touch()

            missing = _missing_kernel_releases(
                root,
                [
                    "6.18.13-200.fc43.x86_64",
                    "6.18.16-200.fc43.x86_64",
                ],
            )

            self.assertEqual(missing, ["6.18.16-200.fc43.x86_64"])

    def test_inspect_candidate_akmods_cache_uses_registry_creds_when_available(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REGISTRY_ACTOR": "actor",
                "REGISTRY_TOKEN": "token",
            },
            clear=False,
        ):
            with patch(
                "ci_tools.main_check_candidate_akmods_cache.skopeo_exists",
                return_value=True,
            ) as skopeo_exists:
                with patch("ci_tools.main_check_candidate_akmods_cache.skopeo_copy") as skopeo_copy:
                    with patch(
                        "ci_tools.main_check_candidate_akmods_cache.load_layer_files_from_oci_layout",
                        return_value=[],
                    ):
                        with patch(
                            "ci_tools.main_check_candidate_akmods_cache.unpack_layer_tarballs",
                        ):
                            status = inspect_candidate_akmods_cache(
                                image_org="danathar",
                                source_repo="kinoite-zfs-bluebuild-akmods",
                                fedora_version="43",
                                kernel_releases=["6.18.16-200.fc43.x86_64"],
                            )

        self.assertFalse(status.reusable)
        skopeo_exists.assert_called_once_with(
            "docker://ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
            creds="actor:token",
        )
        copy_args, copy_kwargs = skopeo_copy.call_args
        self.assertEqual(
            copy_args[0],
            "docker://ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
        )
        self.assertTrue(copy_args[1].startswith("dir:"))
        self.assertEqual(copy_kwargs["creds"], "actor:token")

    def test_write_cache_status_outputs_writes_structured_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "github-output.txt"
            with patch.dict(
                os.environ,
                {
                    "GITHUB_OUTPUT": str(output_path),
                },
                clear=True,
            ):
                write_cache_status_outputs(
                    AkmodsCacheStatus(
                        source_image="ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
                        image_exists=True,
                        missing_releases=("6.18.16-200.fc43.x86_64",),
                    )
                )

            outputs = output_path.read_text(encoding="utf-8")
            self.assertIn("exists=false\n", outputs)
            self.assertIn("status=stale\n", outputs)
            self.assertIn("missing_releases=6.18.16-200.fc43.x86_64\n", outputs)
            self.assertIn(
                "source_image=ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43\n",
                outputs,
            )


if __name__ == "__main__":
    unittest.main()
