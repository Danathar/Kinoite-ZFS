"""
Script: tests/test_main_sign_promoted_stable.py
What: Tests for stable-image signing after candidate promotion.
Doing: Verifies digest-ref construction, missing-key failure, and the exact cosign command sequence without touching a live registry.
Why: Promotion signing moved out of workflow YAML and needs direct coverage now that it is code.
Goal: Keep stable signing behavior explicit, testable, and easy to refactor safely.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ci_tools.common import CiToolError
from ci_tools.main_sign_promoted_stable import (
    sign_promoted_stable,
    stable_image_digest_ref,
    stable_image_tag_ref,
)


class MainSignPromotedStableTests(unittest.TestCase):
    def test_builds_expected_stable_refs(self) -> None:
        self.assertEqual(
            stable_image_tag_ref("danathar", "kinoite-zfs"),
            "docker://ghcr.io/danathar/kinoite-zfs:latest",
        )
        self.assertEqual(
            stable_image_digest_ref("danathar", "kinoite-zfs", "sha256:abc"),
            "ghcr.io/danathar/kinoite-zfs@sha256:abc",
        )

    def test_requires_signing_key(self) -> None:
        with self.assertRaises(CiToolError):
            sign_promoted_stable(
                image_org="danathar",
                image_name="kinoite-zfs",
                registry_actor="actor",
                registry_token="token",
                cosign_private_key="",
            )

    def test_signs_and_verifies_stable_digest(self) -> None:
        calls: list[tuple[list[str], bool, dict[str, str] | None]] = []

        def fake_run_cmd(
            args: list[str],
            *,
            capture_output: bool = True,
            cwd: str | None = None,
            env: dict[str, str] | None = None,
        ) -> str:
            del cwd
            calls.append((args, capture_output, env))
            return ""

        with tempfile.TemporaryDirectory() as temp_dir:
            cosign_pub = Path(temp_dir) / "cosign.pub"
            cosign_pub.write_text("public-key", encoding="utf-8")

            with patch("ci_tools.main_sign_promoted_stable.Path") as path_class:
                # Only the `cosign.pub` existence check matters for this helper.
                path_class.return_value.exists.return_value = True

                stable_ref = sign_promoted_stable(
                    image_org="danathar",
                    image_name="kinoite-zfs",
                    registry_actor="actor",
                    registry_token="token",
                    cosign_private_key="private-key",
                    digest_lookup=lambda _ref: "sha256:stable",
                    command_runner=fake_run_cmd,
                )

        self.assertEqual(stable_ref, "ghcr.io/danathar/kinoite-zfs@sha256:stable")
        self.assertEqual(calls[0][0][:4], ["cosign", "sign", "--yes", "--key"])
        self.assertEqual(calls[0][1], False)
        self.assertEqual(
            calls[0][2],
            {
                "COSIGN_PASSWORD": "",
                "COSIGN_PRIVATE_KEY": "private-key",
            },
        )
        self.assertEqual(calls[1][0][:3], ["cosign", "verify", "--key"])
        self.assertEqual(calls[1][2], None)


if __name__ == "__main__":
    unittest.main()
