"""
Script: tests/test_main_smoke_test_candidate_image.py
What: Tests for the post-build candidate-image smoke-test helper.
Doing: Verifies candidate ref construction plus the command sequence used to validate kernels and ZFS payloads.
Why: Promotion now depends on this helper to gate stable tag updates.
Goal: Keep the smoke-test logic explicit and safe to refactor.
"""

from __future__ import annotations

from pathlib import Path
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
        copied: list[tuple[str, str, str | None]] = []

        def fake_copy(source: str, destination: str, *, creds: str | None = None, retry_times: int = 3) -> None:
            del retry_times
            copied.append((source, destination, creds))

        def fake_unpack(_layers: list[Path], destination: Path) -> None:
            for kernel_release in (
                "6.18.13-200.fc43.x86_64",
                "6.18.16-200.fc43.x86_64",
            ):
                (destination / "lib" / "modules" / kernel_release / "extra" / "zfs").mkdir(
                    parents=True,
                    exist_ok=True,
                )
                (
                    destination
                    / "lib"
                    / "modules"
                    / kernel_release
                    / "extra"
                    / "zfs"
                    / "zfs.ko.xz"
                ).touch()

            (destination / "usr" / "sbin").mkdir(parents=True, exist_ok=True)
            (destination / "usr" / "sbin" / "zfs").touch()
            (destination / "usr" / "sbin" / "zpool").touch()

        candidate_ref = smoke_test_candidate_image(
            image_org="danathar",
            image_name="kinoite-zfs-candidate",
            fedora_version="43",
            git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
            registry_actor="actor",
            registry_token="token",
            digest_lookup=lambda _ref, creds=None: "sha256:candidate",
            image_copier=fake_copy,
            layer_loader=lambda _image_dir: [Path("layer.tar")],
            layer_unpacker=fake_unpack,
        )

        self.assertEqual(
            candidate_ref,
            "ghcr.io/danathar/kinoite-zfs-candidate@sha256:candidate",
        )
        self.assertEqual(
            copied[0][0],
            "docker://ghcr.io/danathar/kinoite-zfs-candidate:ab86cae-43",
        )
        self.assertTrue(copied[0][1].startswith("dir:"))
        self.assertEqual(copied[0][2], "actor:token")

    def test_smoke_test_candidate_image_fails_when_no_kernels_are_present(self) -> None:
        with self.assertRaises(CiToolError):
            smoke_test_candidate_image(
                image_org="danathar",
                image_name="kinoite-zfs-candidate",
                fedora_version="43",
                git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
                registry_actor="actor",
                registry_token="token",
                digest_lookup=lambda _ref, creds=None: "sha256:candidate",
                image_copier=lambda _source, _dest, creds=None, retry_times=3: None,
                layer_loader=lambda _image_dir: [Path("layer.tar")],
                layer_unpacker=lambda _layers, _destination: None,
            )

    def test_smoke_test_candidate_image_fails_when_userland_command_is_missing(self) -> None:
        def fake_unpack(_layers: list[Path], destination: Path) -> None:
            module_dir = (
                destination
                / "lib"
                / "modules"
                / "6.18.16-200.fc43.x86_64"
                / "extra"
                / "zfs"
            )
            module_dir.mkdir(parents=True, exist_ok=True)
            (module_dir / "zfs.ko.xz").touch()
            (destination / "usr" / "sbin").mkdir(parents=True, exist_ok=True)
            (destination / "usr" / "sbin" / "zfs").touch()

        with self.assertRaisesRegex(CiToolError, "missing expected command zpool"):
            smoke_test_candidate_image(
                image_org="danathar",
                image_name="kinoite-zfs-candidate",
                fedora_version="43",
                git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
                registry_actor="actor",
                registry_token="token",
                digest_lookup=lambda _ref, creds=None: "sha256:candidate",
                image_copier=lambda _source, _dest, creds=None, retry_times=3: None,
                layer_loader=lambda _image_dir: [Path("layer.tar")],
                layer_unpacker=fake_unpack,
            )


if __name__ == "__main__":
    unittest.main()
