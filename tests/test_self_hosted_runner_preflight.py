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
import tempfile
import unittest
from unittest.mock import patch

from ci_tools.self_hosted_runner_preflight import cleanup_stale_temp_dirs, run_preflight


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
                    now_timestamp=2_000_000.0,
                )

            self.assertLess(summary.free_bytes, summary.required_free_bytes)
