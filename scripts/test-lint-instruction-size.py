#!/usr/bin/env python3
"""Regression tests for the optional native skill-catalog report."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("lint-instruction-size.py")


class SkillCatalogLaunchTests(unittest.TestCase):
    def run_report(self, binary: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--skill-catalog", str(binary)],
            capture_output=True, text=True, check=False,
        )

    def assert_launch_error(self, binary: Path) -> None:
        result = self.run_report(binary)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"ERROR: could not run skill catalog binary '{binary}'", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_binary_reports_a_concise_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assert_launch_error(Path(directory) / "missing-cake")

    @unittest.skipUnless(os.name == "posix", "requires POSIX executable permissions")
    def test_non_executable_binary_reports_a_concise_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "cake"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o600)
            self.assert_launch_error(binary)

    @unittest.skipUnless(os.name == "posix", "requires a POSIX shell fixture")
    def test_child_exit_status_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "cake"
            binary.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            binary.chmod(0o700)
            result = self.run_report(binary)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
