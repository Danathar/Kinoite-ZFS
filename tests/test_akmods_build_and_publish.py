"""
Script: tests/test_akmods_build_and_publish.py
What: Tests helper functions used by `ci_tools/akmods_build_and_publish.py`.
Doing: Checks kernel-name mapping and generated kernel-cache metadata values.
Why: Catches behavior changes that could break akmods build metadata.
Goal: Keep akmods helper behavior stable over time.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch

from ci_tools import akmods_build_and_publish as script
from ci_tools.akmods_build_and_publish import (
    build_kernel_cache_document,
    kernel_major_minor_patch,
    kernel_name_for_flavor,
)


class AkmodsBuildAndPublishTests(unittest.TestCase):
    def test_kernel_name_for_longterm_flavor(self) -> None:
        self.assertEqual(kernel_name_for_flavor("longterm"), "kernel-longterm")
        self.assertEqual(kernel_name_for_flavor("longterm-lts"), "kernel-longterm")

    def test_kernel_name_for_standard_flavor(self) -> None:
        self.assertEqual(kernel_name_for_flavor("main"), "kernel")

    def test_kernel_major_minor_patch(self) -> None:
        value = kernel_major_minor_patch("6.18.12-200.fc43.x86_64")
        self.assertEqual(value, "6.18.12-200")

    def test_build_kernel_cache_document_default_path(self) -> None:
        payload, cache_path = build_kernel_cache_document(
            kernel_release="6.18.12-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="",
        )

        self.assertEqual(payload["kernel_name"], "kernel")
        self.assertEqual(payload["kernel_major_minor_patch"], "6.18.12-200")
        self.assertTrue(payload["KCWD"].endswith("/main-43/KCWD"))
        self.assertTrue(payload["KCPATH"].endswith("/main-43/KCWD/rpms"))
        self.assertTrue(str(cache_path).endswith("/main-43/KCWD/rpms/cache.json"))

    def test_build_kernel_cache_document_with_kcpath_override(self) -> None:
        payload, cache_path = build_kernel_cache_document(
            kernel_release="6.18.12-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="/custom/rpms",
        )

        self.assertEqual(payload["KCPATH"], "/custom/rpms")
        self.assertEqual(str(cache_path), "/custom/rpms/cache.json")

    def test_build_kernel_cache_document_reuses_fedora_wide_path_across_kernels(self) -> None:
        first_payload, first_cache_path = build_kernel_cache_document(
            kernel_release="6.18.12-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="",
        )
        second_payload, second_cache_path = build_kernel_cache_document(
            kernel_release="6.18.16-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="",
        )

        # The shared `main-43` cache path is intentional: multiple kernel builds
        # in one run accumulate RPMs into one Fedora-wide cache image.
        self.assertEqual(first_payload["KCPATH"], second_payload["KCPATH"])
        self.assertEqual(first_cache_path, second_cache_path)

    def test_main_defers_manifest_until_after_all_kernel_builds(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(script, "AKMODS_WORKTREE", Path(tempdir)):
                with patch.object(
                    script,
                    "kernel_releases_from_env",
                    return_value=[
                        "6.18.13-200.fc43.x86_64",
                        "6.18.16-200.fc43.x86_64",
                    ],
                ):
                    with patch.object(script, "write_kernel_cache_file") as write_cache:
                        with patch.object(script, "run_cmd") as run_cmd:
                            with patch.dict(script.os.environ, {}, clear=False):
                                script.main()
                                self.assertEqual(script.os.environ["BUILDAH_LAYERS"], "false")

        self.assertEqual(
            write_cache.call_args_list,
            [
                call(kernel_release="6.18.13-200.fc43.x86_64"),
                call(kernel_release="6.18.16-200.fc43.x86_64"),
            ],
        )
        self.assertEqual(
            run_cmd.call_args_list,
            [
                call(["just", "login"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "build"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "push"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "build"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "push"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "manifest"], cwd=str(Path(tempdir)), capture_output=False),
            ],
        )


if __name__ == "__main__":
    unittest.main()
