"""
Script: tests/test_akmods_build_and_publish.py
What: Tests helper functions used by `ci_tools/akmods_build_and_publish.py`.
Doing: Checks kernel-name mapping and generated kernel-cache metadata values.
Why: Catches behavior changes that could break akmods build metadata.
Goal: Keep akmods helper behavior stable over time.
"""

from __future__ import annotations

from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
