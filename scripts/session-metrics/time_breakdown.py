#!/usr/bin/env python3
"""Invocation wall-clock context alongside recorded API time, cumulative tool
work, and scheduled retry delays, plus turn pacing, think time between tasks,
and the slowest individual operations.

Wall time comes from telemetry session_summary; API time from api_attempt
total_ms (request + response parsing); cumulative tool work from tool_call
duration_ms; scheduled retry delay from retry_scheduled delay_ms. Tool records
have no execution intervals, and retry records have no observed wait duration,
so the report does not derive an exclusive remainder from them. Hook time is
reported from transcript hook_event records (it overlaps the tool path, so it
is shown for scale, not added to the breakdown). Think time is the transcript
gap between a task_complete and the next task_start in the same session.
"""

import cakelib
from cakelib import fmt_bytes, fmt_int, fmt_ms, fmt_pct, percentile, print_header, print_table


def run(data: cakelib.Dataset) -> None:
    print_header("TIME BREAKDOWN")
    print(cakelib.describe_window(data))

    if not data.invocations:
        print("\nNo telemetry invocations in window.")
        return

    complete = [inv for inv in data.invocations if inv.summary]
    incomplete = len(data.invocations) - len(complete)
    wall = sum(inv.summary["duration_ms"] for inv in complete)
    api = tools = retry_wait = parse = 0
    for inv in data.invocations:
        api += sum(a.get("total_ms", 0) for a in inv.attempts)
        parse += sum(a.get("parse_ms", 0) for a in inv.attempts)
        tools += sum(t.get("duration_ms", 0) for t in inv.tool_calls)
        retry_wait += sum(r.get("delay_ms", 0) for r in inv.retries)

    if complete:
        print(f"\nAcross {fmt_int(len(complete))} complete invocations: "
              f"{fmt_ms(wall)} total wall time.")
    else:
        print("\nNo complete invocation wall time is available in this window.")
    print(f"\nRecorded activity across {fmt_int(len(data.invocations))} telemetry "
          "invocations (includes incomplete invocations):")
    print_table(
        ["activity", "recorded duration", "interpretation"],
        [
            ["model API (request+parse)", fmt_ms(api), "elapsed per attempt"],
            ["  of which response parsing", fmt_ms(parse), "subset of API"],
            ["tool execution (cumulative work)", fmt_ms(tools), "may overlap"],
            ["scheduled retry delay", fmt_ms(retry_wait), "actual wait not measured"],
        ],
    )
    print("\nExclusive remainder is unavailable: tool calls record durations without "
          "execution intervals, and actual retry wait elapsed time is unavailable "
          "because telemetry records only the scheduled delay.")
    if incomplete:
        noun = "invocation" if incomplete == 1 else "invocations"
        verb = "has" if incomplete == 1 else "have"
        print(f"{fmt_int(incomplete)} incomplete {noun} {verb} no session_summary; "
              "only their wall time and turn pacing are unavailable.")

    print("\nCumulative tool work by tool:")
    tel_calls = [tc for inv in data.invocations for tc in inv.tool_calls]
    rows = []
    for tool, calls in sorted(cakelib.group_by(tel_calls, lambda t: t["name"]).items(),
                              key=lambda kv: -sum(c.get("duration_ms", 0) for c in kv[1])):
        tool_time = sum(c.get("duration_ms", 0) for c in calls)
        rows.append([tool, fmt_int(len(calls)), fmt_ms(tool_time),
                     fmt_pct(tool_time, tools)])
    print_table(
        ["tool", "calls", "cumulative time", "share of cumulative tool work"],
        rows,
    )

    print("\nAPI time by model:")
    rows = []
    by_model = cakelib.group_by(data.invocations, lambda inv: inv.model)
    for model, invs in sorted(by_model.items(), key=lambda kv: -len(kv[1])):
        model_api = sum(a.get("total_ms", 0) for inv in invs for a in inv.attempts)
        attempts = sum(len(inv.attempts) for inv in invs)
        rows.append([model, fmt_int(attempts), fmt_ms(model_api), fmt_pct(model_api, api)])
    print_table(["model", "attempts", "time", "share of API time"], rows)

    hook_time = sum(
        e.get("duration_ms") or 0
        for s in data.sessions for e in s.records_in_window(data.cutoff, "hook_event")
    )
    if hook_time:
        print(f"\nHook execution (transcripts, overlaps tool path): {fmt_ms(hook_time)}")

    print("\nTurn pacing (wall per turn, per invocation):")
    pace = [inv.summary["duration_ms"] / inv.summary["turn_count"]
            for inv in complete if inv.summary.get("turn_count")]
    print_table(["p50", "p90", "max"], [[
        fmt_ms(percentile(pace, 50)), fmt_ms(percentile(pace, 90)), fmt_ms(max(pace, default=0)),
    ]])

    # Think time: gap between one task ending and the next starting.
    # task_complete has no timestamp, so a task's end is its task_start
    # timestamp plus the task_complete duration_ms.
    gaps = []
    for s in data.sessions:
        durations = {r.get("task_id"): r.get("duration_ms")
                     for r in s.by_type("task_complete")}
        starts = [(cakelib.parse_ts(r.get("timestamp")), r.get("task_id"))
                  for r in s.by_type("task_start")]
        starts = [(ts, tid) for ts, tid in starts
                  if ts is not None and (data.cutoff is None or ts >= data.cutoff)]
        for (start, task_id), (next_start, _) in zip(starts, starts[1:]):
            duration = durations.get(task_id)
            if duration is None:
                continue
            gap = (next_start - start).total_seconds() * 1000 - duration
            if gap >= 0:
                gaps.append(gap)
    if gaps:
        print(f"\nThink time between tasks (n={fmt_int(len(gaps))}, "
              f"total {fmt_ms(sum(gaps))}):")
        print_table(["p50", "p90", "max"], [[
            fmt_ms(percentile(gaps, 50)), fmt_ms(percentile(gaps, 90)), fmt_ms(max(gaps)),
        ]])

    print("\nSlowest tool calls:")
    slowest = sorted(tel_calls, key=lambda t: -t.get("duration_ms", 0))[:5]
    print_table(
        ["tool", "duration", "output", "session"],
        [[t["name"], fmt_ms(t["duration_ms"]), fmt_bytes(t.get("output_bytes", 0)),
          t.get("session_id", "?")[:8]] for t in slowest],
    )

    print("\nSlowest API attempts:")
    all_attempts = [(inv, a) for inv in data.invocations for a in inv.attempts]
    slowest = sorted(all_attempts, key=lambda ia: -ia[1].get("total_ms", 0))[:5]
    print_table(
        ["model", "duration", "input tokens", "session"],
        [[inv.model, fmt_ms(a["total_ms"]),
          fmt_int((a.get("usage") or {}).get("input_tokens", 0)),
          inv.session_id[:8]] for inv, a in slowest],
    )


def main() -> None:
    ns = cakelib.build_arg_parser(__doc__).parse_args()
    run(cakelib.load(ns))


if __name__ == "__main__":
    main()
