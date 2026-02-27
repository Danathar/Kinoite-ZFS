from __future__ import annotations

import unittest

from ci_tools.common import CiToolError
from ci_tools.main_resolve_build_inputs import choose_base_image_tag


class ChooseBaseImageTagTests(unittest.TestCase):
    def test_keeps_existing_date_stamped_source_tag(self) -> None:
        # If source tag is already immutable-looking, we keep it.
        tag, checked = choose_base_image_tag(
            source_tag="latest-20260227",
            version_label="43.20260227.1",
            fedora_version="43",
            expected_digest="sha256:abc",
            digest_lookup=lambda _tag: "sha256:abc",
        )
        self.assertEqual(tag, "latest-20260227")
        self.assertEqual(checked, ["latest-20260227"])

    def test_derives_tag_from_version_label_and_digest_match(self) -> None:
        digests = {
            "latest-20260227.1": "sha256:match",
            "43-20260227.1": "sha256:other",
        }

        tag, checked = choose_base_image_tag(
            source_tag="latest",
            version_label="43.20260227.1",
            fedora_version="43",
            expected_digest="sha256:match",
            digest_lookup=lambda t: digests.get(t, ""),
        )
        self.assertEqual(tag, "latest-20260227.1")
        self.assertEqual(
            checked,
            ["latest-20260227.1", "latest-20260227.1", "43-20260227.1"],
        )

    def test_rejects_unexpected_version_label(self) -> None:
        with self.assertRaises(CiToolError):
            choose_base_image_tag(
                source_tag="latest",
                version_label="bad-version",
                fedora_version="43",
                expected_digest="sha256:abc",
                digest_lookup=lambda _tag: "",
            )


if __name__ == "__main__":
    unittest.main()
