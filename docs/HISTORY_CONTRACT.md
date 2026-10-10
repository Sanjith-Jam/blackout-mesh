# Issue #25 history contract (v1)
Scope: campus six-service model. Separate hospital/classroom visualizers are not
silently merged into this run. No historical records exist before this delivery.

GET /api/v1/history/runs?site_id=campus returns current_run_id and retained runs.
GET /api/v1/history/records?site_id=campus&run_id=...&kind=telemetry|event|decision
accepts after (exclusive integer sequence), limit (1..1000), start/end (inclusive
ISO timestamps with timezone offsets). Equal timestamps are ordered by seq.
Responses contain items, next_cursor, retention_gap and pruned_through.
Follow next_cursor until null; thereafter poll after the greatest observed seq.
Cursor gaps between kinds are normal. IDs are unique per site/run, and retries
return the existing sequence. Filter ranges are normalized to UTC.

Records retain original UTC timestamp, revision, provenance and stable record_id.
Telemetry is sampled at most once per second, independent of browser connections.
Decisions are recorded only when meaningful state changes; timestamp-only socket
frames do not create decisions. Records include snapshots, configured inputs,
catalog, allocation policy, model identity and observed features/provenance.
Events retain IDs, revision, captured inputs and link to the next recorded decision.
Physical command identity and validated ACK remain null, never inferred from LEDs
or send callbacks. Current backend has no radio translation consuming SystemEvent:
its additive web-only event metadata does not alter the paused serial codec.

Replay means deterministic presentation of persisted evidence/decisions, not
re-running today's model against old inputs. History endpoints never build a
snapshot, advance restoration, issue commands, or call the existing POST replay
endpoint (which injects observations into the LIVE run). What-if/fork creation
is not exposed; it must allocate a new run before future implementation.

SQLite path: PRIORITYGRID_HISTORY_DB, default backend/history.sqlite3 (ignored).
SQLModel 0.0.48 installed successfully on Python 3.14. Indexes cover site/run/seq
and site/run/UTC timestamp; record IDs have a compound uniqueness constraint.
Raw evidence retention: 30 days, trimmed at startup and hourly during recording; no lossy rollups are produced.
The sampling policy aggregates rendered frames, not incident or decision evidence.
retention_gap warns that an old cursor has expired. The recorder uses SiteAuthority.run_id; explicit site run resets rotate the recorder,
and previous runs remain available after restart or reset. No live controller restoration
from history is claimed.

Limitations: dependency #12's transactional state/input journal and #13's server
publication sequence are not implemented upstream. This recorder captures public
events and recorded applied snapshots, not crash-atomic input->decision commits.
History recording occurs only in SiteAuthority.tick after its canonical publication,
never in GET or WebSocket reads. SQLite writes remain synchronous under the
authority lock; bounded writer-queue/crash-atomic integration is a #12 gate. Failures are
surfaced, not replaced by fabricated records. No calibrated hardware ACK trail,
causal model re-execution, cross-site catalogs, schema-generated TS (#14), or
what-if execution is claimed. Do not close #25 until those integration gates land.

## Current-main integration
Recording follows the canonical site run and revision while preserving the upstream
read-only GridState.build_snapshot and single ControlLoop. Event revision fields
remain campus control revisions; decision/telemetry revisions are site revisions
and the complete recorded snapshot retains both. Telemetry timestamps identify
sampling time; state_generated_at retains the original publication time. Generated
publication/site revision changes alone do not create new decision records.
