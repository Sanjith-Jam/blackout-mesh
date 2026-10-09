# AGENTS.md

Offline campus-power decision demo: simulated electrical model, Python authority, real ESP32 radio/LED feedback.
Spec: `PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md` (v1.1). State/handoff: `CONTEXT.md`. Historical planning references are maintained outside this repository.

**Status:** planning docs only. No code, tests or firmware exist until you create and run them.

## Stack

- `backend/` Python + FastAPI, single worker, the only owner of modeled state.
- `frontend/` React + TypeScript + Vite, renders full snapshots.
- `firmware/` Arduino C++ + ESP-NOW.
- Allocation: exact 128-mask enumeration (64 for the legacy fixture) is the oracle; OR-Tools CP-SAT must match it.
- Pin versions only after a successful local install/compile. Never invent pins.

## Commands

Hardware (board B + laptop bench controller, see `hardware/README.md`), run from `hardware/host/`:

- `python -m unittest test_person_b`: protocol, allocator and fault tests with a simulated board B.
- `python controller.py --sim` or `--port COMx`: laptop bench controller (needs `pyserial` for a real port).
- `python hw_check.py COMx`: scripted bench and fault-injection run against a connected board B.
- Flash `hardware/firmware/BoardB_Output` with Arduino ESP32 core 3.3.12, board `esp32:esp32:esp32`, upload speed 115200.

When you add a command, add it here and to README in the same commit.

## Workflow: small commits

1. Pick the next unfinished step from `PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md` dependencies and delivery gates (§14, §15). Break it into commit-sized pieces; one piece = one commit.
2. Read the code you touch and its callers.
3. Make the smallest change that completes the step, plus its check if the logic is nontrivial.
4. Run the relevant checks. Do not commit failing checks.
5. Commit: `git add <specific files>` then `git commit -m "<area>: <what>"`, e.g. `backend: exact allocator with 7 kW test`.
6. Repeat. Do not batch unrelated changes or reformat files you didn't change.

Keep commits under ~200 changed lines where possible. Split refactors from behavior changes. Do not push, amend or rewrite history unless asked.

## Invariants (never break)

1. Power is integer watts. Reject non-finite, out-of-range or wrong-typed JSON, bad IDs, masks and schema versions.
2. Diagnosis/allocation read only observations, configured demand and policy — never scenario labels or simulator truth.
3. Missing data is `unknown`/`null`, never zero.
4. No load served across a known open feeder. Shedding never creates supply.
5. A plan marked feasible never exceeds capacity. Critical shortfall is reported, not a solver failure.
6. Restoration needs fresh evidence and stable capacity. Protective shedding is immediate.
7. Proposed mask, applied simulated state and ACKed LED state are separate fields.
8. Only a validated ACK (current session + device boot + command seq + mask) confirms an LED. Radio send callbacks do not.
9. Late/duplicate/malformed messages never mutate a newer run. Retries reuse the command identity; duplicates are idempotent.
10. Disconnects and restarts visibly mark status stale. A rebooted device reports state before resync.
11. Radio callbacks do minimal work. Serial I/O and solving never block publication or heartbeats.
12. UI labels synthetic power, virtual devices and real radio. No invented accuracy, savings, mesh routing or power delivery.

## Scope

Do not add mandatory trained ML, a broker, a second backend, cloud storage, real power electronics or mesh routing. Prefer stdlib and native browser features. Follow the component layout in plan §6; create modules only as needed.

## Shared contract

Snapshot/API schema changes touch Python models, TypeScript types, fixtures and serial translation in **one** commit. Update the contract and all consumers together.

## Hardware safety

USB-powered low-voltage LEDs only, one resistor each. ESP32 GPIO is 3.3 V. Identify the exact board before choosing pins. Never connect mains, relays or separate 5 V rails. Use the examples shipped with the pinned toolchain. Claim flashing or radio success only with evidence from connected devices.

## Testing

- Cover: allocation constraints/objective, feeder reachability, unknown observations, stale commands/ACKs, restoration. One compact test file to start.
- Deterministic seeds and simulated clocks; host monotonic time for real latency.
- Freeze dev scenarios before held-out evaluation. Report denominators, failures and abstentions.

## Reuse

Reuse research is local-only. Before copying code, check its license at a pinned commit and preserve all required source/license notices in the distributed implementation.

## On-demand tools

Use Graphify and Security Auditor only when explicitly requested.

## Handoff

When a step lands, update `CONTEXT.md` (done, commands run + results, failures, next step). Targets are not results.
