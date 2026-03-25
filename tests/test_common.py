"""
Script: tests/test_common.py
What: Tests for shared helper behavior in `ci_tools/common.py`.
Doing: Verifies GitHub output-file formatting and registry credential lookup.
Why: These helpers sit underneath many workflow commands and should fail clearly.
Goal: Keep workflow I/O handling robust across future refactors.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ci_tools.common import CiToolError, optional_registry_creds, write_github_outputs


class CommonTests(unittest.TestCase):
    def test_optional_registry_creds_uses_explicit_actor_and_token(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REGISTRY_ACTOR": "actor",
                "REGISTRY_TOKEN": "token",
            },
            clear=True,
        ):
            self.assertEqual(optional_registry_creds(), "actor:token")

    def test_optional_registry_creds_falls_back_to_github_actor(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GITHUB_ACTOR": "fallback-actor",
                "REGISTRY_TOKEN": "token",
            },
            clear=True,
        ):
            self.assertEqual(optional_registry_creds(), "fallback-actor:token")

    def test_optional_registry_creds_requires_actor_when_token_is_present(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REGISTRY_TOKEN": "token",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(CiToolError, "Missing registry actor"):
                optional_registry_creds()

    def test_write_github_outputs_writes_single_and_multiline_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "github-output.txt"
            with patch.dict(
                os.environ,
                {
                    "GITHUB_OUTPUT": str(output_path),
                },
                clear=True,
            ):
                write_github_outputs(
                    {
                        "single": "value",
                        "multi": "line-1\nline-2",
                    }
                )

            written = output_path.read_text(encoding="utf-8")
            self.assertIn("single=value\n", written)
            self.assertIn("multi<<__GITHUB_OUTPUT_EOF__\nline-1\nline-2\n__GITHUB_OUTPUT_EOF__\n", written)


if __name__ == "__main__":
    unittest.main()
