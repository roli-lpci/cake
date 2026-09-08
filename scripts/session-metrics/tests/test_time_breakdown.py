#!/usr/bin/env python3
"""Regression tests for honest wall-time reporting in time_breakdown.py.

Run with `just session-metrics-check` or:
  python3 -m unittest discover -s scripts/session-metrics/tests -v
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cakelib
import time_breakdown


def invocation(
    *,
    wall_ms: int | None,
    tool_durations: list[int] | None = None,
    retry_delays: list[int] | None = None,
) -> cakelib.Invocation:
    inv = cakelib.Invocation("session-1", "invocation-1")
    inv.init = {"model": "test-model", "working_directory": "/project"}
    if wall_ms is not None:
        inv.summary = {"duration_ms": wall_ms, "turn_count": 1}
    inv.tool_calls = [
        {
            "name": f"Tool{index}",
            "duration_ms": duration,
            "output_bytes": 0,
            "session_id": inv.session_id,
        }
        for index, duration in enumerate(tool_durations or [], start=1)
    ]
    inv.retries = [
        {"reason": "rate_limit", "delay_ms": delay}
        for delay in retry_delays or []
    ]
    return inv


def report(invocations: list[cakelib.Invocation]) -> str:
    data = cakelib.Dataset(
        sessions=[],
        invocations=invocations,
        sessions_dir=None,
        telemetry_dir=None,
        cutoff=None,
    )
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        time_breakdown.run(data)
    return output.getvalue()


class TimeBreakdownTest(unittest.TestCase):
    def test_concurrent_tool_work_is_not_an_exclusive_wall_share(self):
        output = report([invocation(wall_ms=1000, tool_durations=[800, 800])])

        self.assertIn("tool execution (cumulative work)", output)
        self.assertRegex(output, r"tool execution \(cumulative work\)\s+1\.6s\s+may overlap")
        self.assertNotIn("160.0%", output)
        self.assertNotIn("other (streaming", output)

    def test_sequential_tool_work_keeps_useful_cumulative_context(self):
        output = report([invocation(wall_ms=1000, tool_durations=[300, 400])])

        self.assertRegex(output, r"tool execution \(cumulative work\)\s+700ms\s+may overlap")
        self.assertIn("share of cumulative tool work", output)
        self.assertIn("42.9%", output)
        self.assertIn("57.1%", output)

    def test_scheduled_retry_delay_is_not_reported_as_elapsed_time(self):
        output = report([invocation(wall_ms=1000, retry_delays=[500])])

        self.assertRegex(output, r"scheduled retry delay\s+500ms\s+actual wait not measured")
        self.assertNotIn("50.0%", output)
        self.assertIn("actual retry wait elapsed time is unavailable", output)

    def test_interrupted_invocation_has_no_precise_wall_attribution(self):
        inv = invocation(wall_ms=None, tool_durations=[800])
        inv.attempts = [{"total_ms": 900, "parse_ms": 25}]
        output = report([inv])

        self.assertIn("No complete invocation wall time is available", output)
        self.assertIn("1 incomplete invocation has no session_summary", output)
        self.assertIn("only their wall time and turn pacing are unavailable", output)
        self.assertRegex(output, r"tool execution \(cumulative work\)\s+800ms\s+may overlap")
        self.assertRegex(output, r"Slowest API attempts:[\s\S]+test-model\s+900ms")


if __name__ == "__main__":
    unittest.main()
