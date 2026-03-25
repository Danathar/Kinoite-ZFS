"""
Script: tests/test_main_write_build_provenance.py
What: Tests for the main-workflow provenance manifest helper.
Doing: Verifies candidate/stable digest resolution and the resulting JSON structure.
Why: The provenance artifact is intended to support rollback and replay decisions.
Goal: Keep the written manifest compact, explicit, and stable across refactors.
"""

from __future__ import annotations

import os
from typing import Any, cast
import unittest
from unittest.mock import patch

from ci_tools.main_write_build_provenance import build_provenance_document


class MainWriteBuildProvenanceTests(unittest.TestCase):
    def test_build_provenance_document_records_candidate_and_stable_refs(self) -> None:
        digest_map = {
            "docker://ghcr.io/danathar/kinoite-zfs-bluebuild-akmods-candidate:main-43": "sha256:candidate-akmods",
            "docker://ghcr.io/danathar/kinoite-zfs:latest": "sha256:stable-image",
            "docker://ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43": "sha256:stable-akmods",
        }

        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "Danathar/Kinoite-ZFS",
                "GITHUB_WORKFLOW": "Build And Promote Main Image",
                "GITHUB_RUN_ID": "123",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_RUN_NUMBER": "456",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_SHA": "49c4c8fb32ae59ff9e5b2a1cc6223f72d4cb583d",
                "GITHUB_ACTOR": "Danathar",
            },
            clear=False,
        ):
            document = build_provenance_document(
                image_org="danathar",
                fedora_version="43",
                image_name="kinoite-zfs",
                candidate_image_name="kinoite-zfs-candidate",
                stable_akmods_repo="kinoite-zfs-bluebuild-akmods",
                candidate_akmods_repo="kinoite-zfs-bluebuild-akmods-candidate",
                kernel_releases=["6.19.8-200.fc43.x86_64"],
                base_image_ref="ghcr.io/ublue-os/kinoite-main:latest",
                base_image_name="ghcr.io/ublue-os/kinoite-main",
                base_image_tag="latest",
                base_image_pinned="ghcr.io/ublue-os/kinoite-main@sha256:base",
                base_image_digest="sha256:base",
                build_container_ref="ghcr.io/ublue-os/devcontainer:latest",
                build_container_pinned="ghcr.io/ublue-os/devcontainer@sha256:builder",
                build_container_digest="sha256:builder",
                zfs_minor_version="2.4",
                akmods_upstream_ref="9d13b6950811cdaae2e8ab748c85c5da35810ae3",
                promotion_result="success",
                registry_creds="actor:token",
                candidate_image_digest="sha256:candidate-image",
                digest_lookup=lambda image_ref, creds=None: digest_map[image_ref],
            )
        candidate = cast(dict[str, Any], document["candidate"])
        candidate_image = cast(dict[str, str], candidate["image"])
        candidate_akmods = cast(dict[str, str], candidate["akmods"])
        stable = cast(dict[str, Any], document["stable"])
        stable_image = cast(dict[str, str], stable["image"])
        stable_akmods = cast(dict[str, str], stable["akmods"])

        self.assertEqual(
            candidate_image["digest_ref"],
            "ghcr.io/danathar/kinoite-zfs-candidate@sha256:candidate-image",
        )
        self.assertEqual(
            candidate_akmods["digest"],
            "sha256:candidate-akmods",
        )
        self.assertTrue(cast(bool, stable["promoted"]))
        self.assertEqual(
            stable_image["digest"],
            "sha256:stable-image",
        )
        self.assertEqual(
            stable_akmods["digest"],
            "sha256:stable-akmods",
        )

    def test_build_provenance_document_records_skipped_promotion(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "Danathar/Kinoite-ZFS",
                "GITHUB_WORKFLOW": "Build And Promote Main Image",
                "GITHUB_RUN_ID": "123",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_RUN_NUMBER": "456",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_SHA": "49c4c8fb32ae59ff9e5b2a1cc6223f72d4cb583d",
                "GITHUB_ACTOR": "Danathar",
            },
            clear=False,
        ):
            document = build_provenance_document(
                image_org="danathar",
                fedora_version="43",
                image_name="kinoite-zfs",
                candidate_image_name="kinoite-zfs-candidate",
                stable_akmods_repo="kinoite-zfs-bluebuild-akmods",
                candidate_akmods_repo="kinoite-zfs-bluebuild-akmods-candidate",
                kernel_releases=["6.19.8-200.fc43.x86_64"],
                base_image_ref="ghcr.io/ublue-os/kinoite-main:latest",
                base_image_name="ghcr.io/ublue-os/kinoite-main",
                base_image_tag="latest",
                base_image_pinned="ghcr.io/ublue-os/kinoite-main@sha256:base",
                base_image_digest="sha256:base",
                build_container_ref="ghcr.io/ublue-os/devcontainer:latest",
                build_container_pinned="ghcr.io/ublue-os/devcontainer@sha256:builder",
                build_container_digest="sha256:builder",
                zfs_minor_version="2.4",
                akmods_upstream_ref="9d13b6950811cdaae2e8ab748c85c5da35810ae3",
                promotion_result="skipped",
                registry_creds="actor:token",
                candidate_image_digest="sha256:candidate-image",
                digest_lookup=lambda image_ref, creds=None: {
                    "docker://ghcr.io/danathar/kinoite-zfs-bluebuild-akmods-candidate:main-43": "sha256:candidate-akmods",
                }[image_ref],
            )
        stable = cast(dict[str, Any], document["stable"])

        self.assertFalse(cast(bool, stable["promoted"]))
        self.assertEqual(cast(str, stable["promotion_result"]), "skipped")
