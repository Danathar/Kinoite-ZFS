"""
Script: tests/test_main_smoke_test_candidate_image.py
What: Tests for the post-build candidate-image smoke-test helper.
Doing: Verifies candidate ref construction plus the command sequence used to validate kernels and ZFS payloads.
Why: Promotion now depends on this helper to gate stable tag updates.
Goal: Keep the smoke-test logic explicit and safe to refactor.
"""

from __future__ import annotations

import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from ci_tools.common import CiToolError
from ci_tools.main_smoke_test_candidate_image import (
    CandidateImageLayerScanResult,
    candidate_image_digest_ref,
    candidate_image_tag_ref,
    inspect_candidate_image_layers,
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

    def test_inspect_candidate_image_layers_tracks_whiteouts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_layer = root / "layer-1.tar"
            second_layer = root / "layer-2.tar"

            with tarfile.open(first_layer, "w") as tar_handle:
                for file_name in (
                    "usr/sbin/zfs",
                    "usr/sbin/zpool",
                    "lib/modules/6.19.8-200.fc43.x86_64/extra/zfs/zfs.ko.xz",
                ):
                    entry = tarfile.TarInfo(file_name)
                    payload = b"payload"
                    entry.size = len(payload)
                    tar_handle.addfile(entry, io.BytesIO(payload))

            with tarfile.open(second_layer, "w") as tar_handle:
                whiteout = tarfile.TarInfo("usr/sbin/.wh.zfs")
                whiteout.size = 0
                tar_handle.addfile(whiteout, io.BytesIO(b""))

                replacement = tarfile.TarInfo("usr/bin/zfs")
                payload = b"payload"
                replacement.size = len(payload)
                tar_handle.addfile(replacement, io.BytesIO(payload))

            result = inspect_candidate_image_layers(
                [first_layer, second_layer],
                expected_kernel_releases=["6.19.8-200.fc43.x86_64"],
            )

        self.assertEqual(result.kernel_releases, ("6.19.8-200.fc43.x86_64",))
        self.assertEqual(result.command_names, ("zfs", "zpool"))

    def test_smoke_test_candidate_image_validates_userland_and_each_kernel(self) -> None:
        copied: list[tuple[str, str, str | None]] = []

        def fake_copy(source: str, destination: str, *, creds: str | None = None, retry_times: int = 3) -> None:
            del retry_times
            copied.append((source, destination, creds))

        result = smoke_test_candidate_image(
            image_org="danathar",
            image_name="kinoite-zfs-candidate",
            fedora_version="43",
            git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
            registry_actor="actor",
            registry_token="token",
            expected_kernel_releases=[
                "6.18.13-200.fc43.x86_64",
                "6.18.16-200.fc43.x86_64",
            ],
            digest_lookup=lambda _ref, creds=None: "sha256:candidate",
            image_copier=fake_copy,
            layer_loader=lambda _image_dir: [Path("layer.tar")],
            layer_inspector=lambda _layers, expected_kernel_releases=None: CandidateImageLayerScanResult(
                kernel_releases=tuple(expected_kernel_releases or ()),
                command_names=("zfs", "zpool"),
            ),
        )

        self.assertEqual(
            result.candidate_ref,
            "ghcr.io/danathar/kinoite-zfs-candidate@sha256:candidate",
        )
        self.assertEqual(result.candidate_digest, "sha256:candidate")
        self.assertEqual(
            result.kernel_releases,
            (
                "6.18.13-200.fc43.x86_64",
                "6.18.16-200.fc43.x86_64",
            ),
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
                expected_kernel_releases=["6.18.16-200.fc43.x86_64"],
                digest_lookup=lambda _ref, creds=None: "sha256:candidate",
                image_copier=lambda _source, _dest, creds=None, retry_times=3: None,
                layer_loader=lambda _image_dir: [Path("layer.tar")],
                layer_inspector=lambda _layers, expected_kernel_releases=None: CandidateImageLayerScanResult(
                    kernel_releases=tuple(),
                    command_names=("zfs", "zpool"),
                ),
            )

    def test_smoke_test_candidate_image_fails_when_userland_command_is_missing(self) -> None:
        with self.assertRaisesRegex(CiToolError, "missing expected command zpool"):
            smoke_test_candidate_image(
                image_org="danathar",
                image_name="kinoite-zfs-candidate",
                fedora_version="43",
                git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
                registry_actor="actor",
                registry_token="token",
                expected_kernel_releases=["6.18.16-200.fc43.x86_64"],
                digest_lookup=lambda _ref, creds=None: "sha256:candidate",
                image_copier=lambda _source, _dest, creds=None, retry_times=3: None,
                layer_loader=lambda _image_dir: [Path("layer.tar")],
                layer_inspector=lambda _layers, expected_kernel_releases=None: CandidateImageLayerScanResult(
                    kernel_releases=tuple(expected_kernel_releases or ()),
                    command_names=("zfs",),
                ),
            )

    def test_smoke_test_candidate_image_fails_when_expected_kernel_payload_is_missing(self) -> None:
        with self.assertRaisesRegex(CiToolError, "missing a ZFS module payload for kernels 6.18.16-200.fc43.x86_64"):
            smoke_test_candidate_image(
                image_org="danathar",
                image_name="kinoite-zfs-candidate",
                fedora_version="43",
                git_sha="ab86cae4bbff15de6185e9fbb31c90fa00a08ff6",
                registry_actor="actor",
                registry_token="token",
                expected_kernel_releases=[
                    "6.18.13-200.fc43.x86_64",
                    "6.18.16-200.fc43.x86_64",
                ],
                digest_lookup=lambda _ref, creds=None: "sha256:candidate",
                image_copier=lambda _source, _dest, creds=None, retry_times=3: None,
                layer_loader=lambda _image_dir: [Path("layer.tar")],
                layer_inspector=lambda _layers, expected_kernel_releases=None: CandidateImageLayerScanResult(
                    kernel_releases=("6.18.13-200.fc43.x86_64",),
                    command_names=("zfs", "zpool"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
