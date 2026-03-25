"""
Script: tests/test_prepare_validation_build.py
What: Tests for the shared non-main validation preparation command.
Doing: Mocks resolved inputs and cache status so we can check success/failure behavior without live registry calls.
Why: Branch and PR workflows now depend on one shared command to pin inputs and fail closed when shared akmods are stale.
Goal: Keep that read-only validation path explicit and safe.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from ci_tools.common import CiToolError
from ci_tools.main_check_candidate_akmods_cache import AkmodsCacheStatus
from ci_tools.main_resolve_build_inputs import BuildInputResolution, ResolvedBuildInputs
from ci_tools.prepare_validation_build import main


def _resolved_inputs() -> BuildInputResolution:
    """Return one realistic resolved-input snapshot for validation tests."""

    return BuildInputResolution(
        inputs=ResolvedBuildInputs(
            version="43",
            kernel_release="6.18.16-200.fc43.x86_64",
            kernel_releases=(
                "6.18.13-200.fc43.x86_64",
                "6.18.16-200.fc43.x86_64",
            ),
            base_image_ref="ghcr.io/ublue-os/kinoite-main:latest",
            base_image_name="ghcr.io/ublue-os/kinoite-main",
            base_image_tag="latest-20260307.1",
            base_image_pinned="ghcr.io/ublue-os/kinoite-main@sha256:base",
            base_image_digest="sha256:base",
            build_container_ref="ghcr.io/ublue-os/devcontainer:latest",
            build_container_pinned="ghcr.io/ublue-os/devcontainer@sha256:build",
            build_container_digest="sha256:build",
            zfs_minor_version="2.4",
            akmods_upstream_ref="abcdef123456",
            use_input_lock=False,
            lock_file_path="ci/inputs.lock.json",
        ),
        label_kernel_release="6.18.16-200.fc43.x86_64",
        candidate_tags=("latest-20260307.1",),
    )


class PrepareValidationBuildTests(unittest.TestCase):
    def test_writes_outputs_and_accepts_reusable_cache(self) -> None:
        resolution = _resolved_inputs()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "github-output.txt")
            with patch.dict(
                os.environ,
                {
                    "GITHUB_OUTPUT": output_path,
                    "GITHUB_REPOSITORY_OWNER": "Danathar",
                    "AKMODS_REPO": "kinoite-zfs-bluebuild-akmods",
                },
                clear=False,
            ):
                with patch(
                    "ci_tools.prepare_validation_build.resolve_build_inputs",
                    return_value=resolution,
                ):
                    with patch(
                        "ci_tools.prepare_validation_build.inspect_candidate_akmods_cache",
                        return_value=AkmodsCacheStatus(
                            source_image="ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
                            image_exists=True,
                            missing_releases=(),
                        ),
                    ) as inspect_cache:
                        main()

            outputs = Path(output_path).read_text(encoding="utf-8")
            self.assertIn("version=43", outputs)
            self.assertIn("kernel_release=6.18.16-200.fc43.x86_64", outputs)
            self.assertIn("kernel_releases=6.18.13-200.fc43.x86_64 6.18.16-200.fc43.x86_64", outputs)
            self.assertIn("base_image_tag=latest-20260307.1", outputs)

            inspect_cache.assert_called_once_with(
                image_org="danathar",
                source_repo="kinoite-zfs-bluebuild-akmods",
                fedora_version="43",
                kernel_releases=["6.18.13-200.fc43.x86_64", "6.18.16-200.fc43.x86_64"],
            )

    def test_fails_closed_when_shared_cache_is_missing_or_stale(self) -> None:
        resolution = _resolved_inputs()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "github-output.txt")
            with patch.dict(
                os.environ,
                {
                    "GITHUB_OUTPUT": output_path,
                    "GITHUB_REPOSITORY_OWNER": "Danathar",
                    "AKMODS_REPO": "kinoite-zfs-bluebuild-akmods",
                },
                clear=False,
            ):
                with patch(
                    "ci_tools.prepare_validation_build.resolve_build_inputs",
                    return_value=resolution,
                ):
                    with patch(
                        "ci_tools.prepare_validation_build.inspect_candidate_akmods_cache",
                        return_value=AkmodsCacheStatus(
                            source_image="ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
                            image_exists=True,
                            missing_releases=("6.18.16-200.fc43.x86_64",),
                        ),
                    ):
                        with self.assertRaises(CiToolError) as context:
                            main()

            self.assertIn(
                "ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
                str(context.exception),
            )
            self.assertIn("rebuild_akmods=true", str(context.exception))


if __name__ == "__main__":
    unittest.main()
