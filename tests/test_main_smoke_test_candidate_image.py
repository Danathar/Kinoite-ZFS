"""
Script: tests/test_main_smoke_test_candidate_image.py
What: Tests for the post-build candidate-image smoke-test helper.
Doing: Verifies candidate ref construction plus the command sequence used to validate kernels and ZFS payloads.
Why: Promotion now depends on this helper to gate stable tag updates.
Goal: Keep the smoke-test logic explicit and safe to refactor.
"""

from __future__ import annotations

import unittest

from ci_tools.common import CiToolError
from ci_tools.main_smoke_test_candidate_image import (
    candidate_image_digest_ref,
    candidate_image_tag_ref,
    smoke_test_candidate_image,
)


class MainSmokeTestCandidateImageTests(unittest.TestCase):
    def test_builds_expected_candidate_refs(self) -> None:
        self.assertEqual(
            candidate_image_tag_ref("danathar", "kinoite-zfs-candidate", "43", "ab86cae"),
            "docker://ghcr.io/danathar/kinoite-zfs-candidate:ab86cae-43",
        )
        self.assertEqual(
            candidate_image_digest_ref(
                "danathar",
                "kinoite-zfs-candidate",
                "sha256:abc",
            ),
            "ghcr.io/danathar/kinoite-zfs-candidate@sha256:abc",
        )

    def test_smoke_test_candidate_image_validates_userland_and_each_kernel(self) -> None:
        calls: list[list[str]] = []

        def fake_run_cmd(
            args: list[str],
            *,
            capture_output: bool = True,
            cwd: str | None = None,
            env: dict[str, str] | None = None,
        ) -> str:
            del capture_output, cwd, env
            calls.append(args)
            if "find /lib/modules -mindepth 1 -maxdepth 1 -type d" in args[-1]:
                return "6.18.13-200.fc43.x86_64\n6.18.16-200.fc43.x86_64\n"
            return ""

        candidate_ref = smoke_test_candidate_image(
            image_org="danathar",
            image_name="kinoite-zfs-candidate",
            fedora_version="43",
            git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
            registry_actor="actor",
            registry_token="token",
            digest_lookup=lambda _ref, creds=None: "sha256:candidate",
            command_runner=fake_run_cmd,
        )

        self.assertEqual(
            candidate_ref,
            "ghcr.io/danathar/kinoite-zfs-candidate@sha256:candidate",
        )
        self.assertEqual(
            calls[0],
            [
                "podman",
                "pull",
                "--quiet",
                "--creds",
                "actor:token",
                "ghcr.io/danathar/kinoite-zfs-candidate@sha256:candidate",
            ],
        )
        self.assertIn("rpm -q zfs kmod-zfs >/dev/null", calls[2][-1])
        self.assertIn("/lib/modules/6.18.13-200.fc43.x86_64/extra/zfs", calls[3][-1])
        self.assertIn("/lib/modules/6.18.16-200.fc43.x86_64/extra/zfs", calls[4][-1])

    def test_smoke_test_candidate_image_fails_when_no_kernels_are_present(self) -> None:
        def fake_run_cmd(
            args: list[str],
            *,
            capture_output: bool = True,
            cwd: str | None = None,
            env: dict[str, str] | None = None,
        ) -> str:
            del capture_output, cwd, env
            if "find /lib/modules -mindepth 1 -maxdepth 1 -type d" in args[-1]:
                return ""
            return ""

        with self.assertRaises(CiToolError):
            smoke_test_candidate_image(
                image_org="danathar",
                image_name="kinoite-zfs-candidate",
                fedora_version="43",
                git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
                registry_actor="actor",
                registry_token="token",
                digest_lookup=lambda _ref, creds=None: "sha256:candidate",
                command_runner=fake_run_cmd,
            )


if __name__ == "__main__":
    unittest.main()
