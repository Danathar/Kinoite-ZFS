from __future__ import annotations

import unittest

from ci_tools.beta_compute_branch_metadata import build_branch_metadata, sanitize_branch_name


class BranchMetadataTests(unittest.TestCase):
    def test_sanitizes_branch_name(self) -> None:
        # Replace unsupported characters and lowercase the name.
        self.assertEqual(sanitize_branch_name("Feature/My Branch!"), "feature-my-branch")

    def test_uses_fallback_when_branch_sanitizes_to_empty(self) -> None:
        self.assertEqual(sanitize_branch_name("!!!"), "branch")

    def test_clamps_long_names(self) -> None:
        long_branch = "a" * 300
        akmods_public_tag_prefix = build_branch_metadata(long_branch)
        self.assertLessEqual(len(akmods_public_tag_prefix), 120)
        self.assertTrue(akmods_public_tag_prefix.startswith("br-"))


if __name__ == "__main__":
    unittest.main()
