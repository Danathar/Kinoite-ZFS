"""
Script: tests/test_self_hosted_runner_preflight.py
What: Tests for the self-hosted runner hygiene/preflight helper.
Doing: Verifies stale temp cleanup rules and the free-space failure threshold.
Why: Preflight should stay predictable because multiple trusted workflows depend on it.
Goal: Keep runner cleanup targeted and fail early on real disk pressure.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ci_tools.self_hosted_runner_preflight import (
    BYTES_PER_GIB,
    cleanup_stale_temp_dirs,
    prune_unused_podman_images,
    run_preflight,
)


class SelfHostedRunnerPreflightTests(unittest.TestCase):
    def test_cleanup_stale_temp_dirs_removes_only_old_repo_owned_dirs(self) -> None:
        now_timestamp = 2_000_000.0

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            stale = temp_root / "candidate-image-smoke-stale"
            fresh = temp_root / "akmods-merge-fresh"
            unrelated = temp_root / "not-ours"

            for path in (stale, fresh, unrelated):
                path.mkdir()
                (path / "payload").write_text("payload", encoding="utf-8")

            os.utime(stale, (now_timestamp - 30 * 3600, now_timestamp - 30 * 3600))
            os.utime(fresh, (now_timestamp - 1 * 3600, now_timestamp - 1 * 3600))
            os.utime(unrelated, (now_timestamp - 30 * 3600, now_timestamp - 30 * 3600))

            summary = cleanup_stale_temp_dirs(
                temp_root,
                retention_hours=24,
                now_timestamp=now_timestamp,
            )

            self.assertEqual(summary.removed_paths, (str(stale),))
            self.assertGreater(summary.reclaimed_bytes, 0)
            self.assertFalse(stale.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(unrelated.exists())

    def test_run_preflight_raises_when_free_space_is_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            host_root = Path(temp_dir)

            with patch(
                "shutil.disk_usage",
                return_value=shutil._ntuple_diskusage(total=100, used=95, free=5),
            ):
                summary = run_preflight(
                    workspace=workspace,
                    host_root=host_root,
                    min_free_gib=1,
                    retention_hours=24,
                    prune_podman_images=False,
                    now_timestamp=2_000_000.0,
                )

            self.assertLess(summary.free_bytes, summary.required_free_bytes)

    def test_run_preflight_prunes_old_unused_podman_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            host_root = Path(temp_dir)
            commands: list[list[str]] = []

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="image-one\nimage-two\n",
                    stderr="",
                )

            disk_usage_values = [
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=90 * BYTES_PER_GIB,
                    free=10 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=86 * BYTES_PER_GIB,
                    free=14 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=86 * BYTES_PER_GIB,
                    free=14 * BYTES_PER_GIB,
                ),
            ]

            with (
                patch("ci_tools.self_hosted_runner_preflight.shutil.which", return_value="/usr/bin/podman"),
                patch("ci_tools.self_hosted_runner_preflight.subprocess.run", side_effect=fake_run),
                patch(
                    "ci_tools.self_hosted_runner_preflight.shutil.disk_usage",
                    side_effect=disk_usage_values,
                ),
            ):
                summary = run_preflight(
                    workspace=workspace,
                    host_root=host_root,
                    min_free_gib=12,
                    retention_hours=24,
                    prune_podman_images=True,
                    podman_image_retention_hours=6,
                    aggressive_podman_prune_on_low_space=True,
                    now_timestamp=2_000_000.0,
                )

            self.assertEqual(
                commands,
                [
                    [
                        "podman",
                        "image",
                        "prune",
                        "--all",
                        "--force",
                        "--build-cache",
                        "--filter",
                        "until=6h",
                    ]
                ],
            )
            self.assertEqual(summary.free_bytes, 14 * BYTES_PER_GIB)
            self.assertEqual(len(summary.podman_prunes), 1)
            self.assertEqual(summary.podman_prunes[0].removed_references, 2)
            self.assertEqual(summary.podman_prunes[0].reclaimed_bytes, 4 * BYTES_PER_GIB)

    def test_podman_image_prune_retries_without_build_cache_on_older_podman(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            commands: list[list[str]] = []

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                if "--build-cache" in command:
                    raise subprocess.CalledProcessError(
                        125,
                        command,
                        stderr="Error: unknown flag: --build-cache\n",
                    )
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="image-one\n",
                    stderr="",
                )

            disk_usage_values = [
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=90 * BYTES_PER_GIB,
                    free=10 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=85 * BYTES_PER_GIB,
                    free=15 * BYTES_PER_GIB,
                ),
            ]

            with (
                patch("ci_tools.self_hosted_runner_preflight.shutil.which", return_value="/usr/bin/podman"),
                patch("ci_tools.self_hosted_runner_preflight.subprocess.run", side_effect=fake_run),
                patch(
                    "ci_tools.self_hosted_runner_preflight.shutil.disk_usage",
                    side_effect=disk_usage_values,
                ),
            ):
                summary = prune_unused_podman_images(
                    workspace=workspace,
                    older_than_hours=24,
                )

            self.assertEqual(
                commands,
                [
                    [
                        "podman",
                        "image",
                        "prune",
                        "--all",
                        "--force",
                        "--build-cache",
                        "--filter",
                        "until=24h",
                    ],
                    [
                        "podman",
                        "image",
                        "prune",
                        "--all",
                        "--force",
                        "--filter",
                        "until=24h",
                    ],
                ],
            )
            self.assertEqual(summary.command, tuple(commands[1]))
            self.assertEqual(summary.removed_references, 1)
            self.assertEqual(summary.reclaimed_bytes, 5 * BYTES_PER_GIB)

    def test_run_preflight_aggressively_prunes_when_old_images_do_not_free_enough(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            host_root = Path(temp_dir)
            commands: list[list[str]] = []
            stdout_values = iter(["", "image-one\n"])

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=next(stdout_values),
                    stderr="",
                )

            disk_usage_values = [
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=90 * BYTES_PER_GIB,
                    free=10 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=90 * BYTES_PER_GIB,
                    free=10 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=90 * BYTES_PER_GIB,
                    free=10 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=90 * BYTES_PER_GIB,
                    free=10 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=70 * BYTES_PER_GIB,
                    free=30 * BYTES_PER_GIB,
                ),
                shutil._ntuple_diskusage(
                    total=100 * BYTES_PER_GIB,
                    used=70 * BYTES_PER_GIB,
                    free=30 * BYTES_PER_GIB,
                ),
            ]

            with (
                patch("ci_tools.self_hosted_runner_preflight.shutil.which", return_value="/usr/bin/podman"),
                patch("ci_tools.self_hosted_runner_preflight.subprocess.run", side_effect=fake_run),
                patch(
                    "ci_tools.self_hosted_runner_preflight.shutil.disk_usage",
                    side_effect=disk_usage_values,
                ),
            ):
                summary = run_preflight(
                    workspace=workspace,
                    host_root=host_root,
                    min_free_gib=20,
                    retention_hours=24,
                    prune_podman_images=True,
                    podman_image_retention_hours=24,
                    aggressive_podman_prune_on_low_space=True,
                    now_timestamp=2_000_000.0,
                )

            self.assertEqual(
                commands,
                [
                    [
                        "podman",
                        "image",
                        "prune",
                        "--all",
                        "--force",
                        "--build-cache",
                        "--filter",
                        "until=24h",
                    ],
                    [
                        "podman",
                        "image",
                        "prune",
                        "--all",
                        "--force",
                        "--build-cache",
                    ],
                ],
            )
            self.assertEqual(summary.free_bytes, 30 * BYTES_PER_GIB)
            self.assertEqual(len(summary.podman_prunes), 2)
            self.assertEqual(summary.podman_prunes[0].removed_references, 0)
            self.assertEqual(summary.podman_prunes[1].removed_references, 1)
