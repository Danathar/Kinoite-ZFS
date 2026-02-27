"""
Script: tests/test_main_publish_candidate_akmods_alias.py
What: Unit tests for candidate akmods alias tag-candidate selection.
Doing: Verifies full-kernel preference and architecture-trimmed fallback behavior.
Why: Prevents tag-resolution regressions in candidate akmods alias publication.
Goal: Keep candidate alias selection deterministic and compatible with expected tag formats.
"""

from __future__ import annotations

import unittest

from ci_tools.main_publish_candidate_akmods_alias import kernel_source_tag_candidates


class MainPublishCandidateAkmodsAliasTests(unittest.TestCase):
    def test_prefers_full_kernel_tag(self) -> None:
        candidates = kernel_source_tag_candidates(
            fedora_version="43",
            kernel_release="6.18.13-200.fc43.x86_64",
        )
        self.assertEqual(candidates[0], "main-43-6.18.13-200.fc43.x86_64")

    def test_includes_no_arch_fallback_for_known_arch_suffix(self) -> None:
        candidates = kernel_source_tag_candidates(
            fedora_version="43",
            kernel_release="6.18.13-200.fc43.x86_64",
        )
        self.assertEqual(candidates[1], "main-43-6.18.13-200.fc43")

    def test_no_arch_fallback_not_added_for_unknown_suffix(self) -> None:
        candidates = kernel_source_tag_candidates(
            fedora_version="43",
            kernel_release="6.18.13-200.fc43.custom",
        )
        self.assertEqual(candidates, ["main-43-6.18.13-200.fc43.custom"])


if __name__ == "__main__":
    unittest.main()
