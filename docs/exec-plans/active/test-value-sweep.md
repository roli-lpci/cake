## Sweep low-value and implementation-coupled tests

This ExecPlan is a living document, maintained per `docs/workflow/exec-plans.md`. It tracks issue #502, "Sweep low-value and implementation-coupled tests."

## Purpose / Big Picture

Cake's tests should protect behavior that users, providers, extensions, and maintainers rely on: CLI and exit contracts, wire formats, persistence, security boundaries, concurrency, and meaningful error handling. Tests that only restate private source structure, prove a trivial derived value, duplicate a stronger test, or assert a tautology consume maintenance time while providing little regression detection. This sweep will review the Rust tests in `src/` and `tests/`, remove only candidates with a concrete value rationale, and simplify production seams that exist solely for deleted tests. The resulting test suite will be smaller without weakening the compatibility and security contracts above.

## Progress

- [x] (2026-09-05) Confirmed a clean `master` synchronized with `origin/master` at `3bebb6e`.
- [x] (2026-09-05) Created and claimed GitHub issue #502; added this plan as the implementation record.
- [ ] Inventory all test modules and classify candidate tests by behavioral value.
- [ ] Remove confirmed low-value, tautological, implementation-coupled, and duplicate tests; record exact counts and files.
- [ ] Simplify production code only where a removed test was the sole reason for an artificial seam, preserving behavior.
- [ ] Run focused tests and the routed Rust gates, including proportionate full/coverage checks.
- [ ] Update issue acceptance notes and plan outcomes, move this plan to `docs/exec-plans/completed/`, push the branch, and open a pull request.

## Surprises & Discoveries

- The repository contains 65 Rust files with test attributes, 1,516 test attributes/locations reported by the initial search, 4,081 assertion lines, and 125 snapshot-related calls; the initial counts include production and test support code and will not be used as final removal counts.
- The project board currently has more than 200 items. The checked-in `scripts/claim-issue.sh` only reads 200 items, so issue #502 had to be claimed with the same documented GraphQL status mutation after verifying the item at a larger limit. This is workflow tooling context, not part of the code change.

## Decision Log

- Decision: Treat this as an L-sized cross-cutting maintenance task requiring an ExecPlan. Rationale: the audit spans all Rust test surfaces and can affect production seams, while the requested outcome requires exact category/file accounting and compatibility-focused verification. Date/Author: 2026-09-05, coding agent.
- Decision: Remove a test only when its assertions do not add meaningful behavioral protection or are fully subsumed by a stronger test. Preserve unit tests when they exercise parsing, validation, boundary conditions, error semantics, security, concurrency, serialization, or other observable behavior. Rationale: test location is not itself evidence of low value. Date/Author: 2026-09-05, coding agent.
- Decision: Do not replace deleted low-value tests with new tests solely to preserve coverage. Rationale: coverage is a signal, not the purpose of a test; the requested sweep prioritizes regression value. Date/Author: 2026-09-05, coding agent.

## Outcomes & Retrospective

To be completed before opening the pull request. It will state the exact number of removed tests by category and file, any production simplifications, verification results, and remaining risks.

## Context and Orientation

Cake is a Rust 2024 binary-only CLI. Test code lives in inline `#[cfg(test)]` modules, dedicated `*_tests.rs` modules under `src/`, and integration tests under `tests/`. The compatibility authorities are `src/main.rs` and `src/cli/` for CLI shape and output, `src/clients/` and snapshots for provider wire formats, `src/clients/tools/` plus security documentation for tool and sandbox behavior, `src/config/` and `src/prompts/` for configuration and prompt resolution, and `src/types/session.rs` plus snapshots for persisted records. `ARCHITECTURE.md` describes the boundaries that must remain covered.

The audit will prioritize clear source-string checks, tests that merely assert a private implementation name or structure, trivial getters/derived accessors, tautologies, and duplicate scenarios. It will not delete a test merely because it is a unit test, has a short body, checks a string, or contributes to coverage. Protocol and user-facing strings remain valuable when they are part of a documented contract or distinguish an externally observable failure.

## Plan of Work

First, inspect every test module and build a candidate ledger from test names, assertions, snapshots, and production seams. For each candidate, identify the behavior it protects and whether another retained test or an integration contract already covers it. Exclude security, wire, persistence, CLI/exit, hook/toolbox, scheduling, concurrency, boundary, and meaningful error-path tests from deletion unless the evidence shows exact duplication.

Next, edit only the affected test files to remove confirmed candidates and their now-unused helpers/imports. If a candidate is a duplicate, retain the test with the stronger observable assertion and explain the choice in the issue/PR accounting. If a deleted test was the sole consumer of a production-only helper or seam, simplify that production code in the same focused diff; do not change public behavior or use the sweep to refactor unrelated code.

Finally, format and run focused tests for touched modules, then run `just check`. Because this is a Rust and test change, use `just check-full` or the narrower coverage/change-risk commands available in the repository if the full local run is feasible; report exact skipped checks and reasons. Review the final diff for accidental behavior changes, compatibility regressions, and unnecessary deletion. Complete the issue notes and archive this plan before opening the PR.

## Concrete Steps

All commands run from `/Users/travisennis/Projects/cake/cake-1`.

Use `rg`, `find`, `wc`, and targeted reads to enumerate test functions, source-string assertions, snapshots, duplicate helper setup, and test-only production seams. Maintain a local candidate ledger during the audit; it need not be committed unless a reviewer needs it. For each edit, run a focused command such as `cargo test <module-or-test-filter>` and inspect the diff with `git diff --check` and `git diff --stat`.

After implementation, run:

```
cargo fmt -- --check
cargo test --all-features --quiet
just check
```

Run `just check-full` when time and local tool availability permit. If the full coverage/change-risk suite is run separately, use the repository recipes from `justfile` and record the exact result. Before handoff, inspect `git status --short`, `git diff --check`, and `git diff --stat`, push `test/test-value-sweep`, and open the PR with `just pr labels="type:test,area:quality" body=<body-file> issue=502` after acceptance notes and this plan are complete.

## Validation and Acceptance

Acceptance is behavioral and accounting-focused. The retained suite must still exercise the documented CLI and exit behavior, provider request/response translations and snapshots, session JSONL records, settings and prompt precedence, tool argument/path validation, sandbox fail-closed behavior, hook and toolbox protocols, scheduling/concurrency limits, and meaningful errors. `cargo test --all-features --quiet` and `just check` must pass. The final report and issue comment must enumerate every removed test with category and repository-relative file, state why it was low-value or duplicated, identify every production simplification, and list any checks that were not run.

No behavior or security contract is intentionally changed. Any test failure caused by a production behavior difference blocks handoff rather than being fixed by weakening the assertion.

## Idempotence and Recovery

Inventory and test commands are safe to repeat. Test deletions are recoverable with Git while the branch retains history; before broad edits, commit a coherent checkpoint so a candidate can be restored without reverting unrelated work. If formatting or checks expose an accidental behavior change, restore only the affected paths from the last branch commit, re-read the candidate's rationale, and narrow the deletion. Do not reset or clean unrelated user changes. Do not hand-edit generated `ci/cargo-crap-baseline.json`; if a production simplification changes its metrics, regenerate it with `just change-risk-baseline`.

## Artifacts and Notes

The final PR body and issue #502 acceptance comment will include an exact removal ledger, simplification summary, compatibility assessment, verification commands/results, and skipped checks. This plan's completed Outcomes & Retrospective will preserve the same conclusions before the plan is moved to `docs/exec-plans/completed/`.

## Interfaces and Dependencies

The sweep relies on Rust's existing test harness, `cargo test`, `cargo insta` snapshots where applicable, and the repository's `just` recipes. It must preserve the public CLI binary, OpenAI-compatible backend request/response shapes, session JSONL and stream records, hook/toolbox protocols, sandbox policy, and all documented exit behavior. No dependency or wire-format change is in scope.
