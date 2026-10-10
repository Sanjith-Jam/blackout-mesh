# Issue #12 delivery — durable audit and recovery

**Status:** implemented on `codex/remaining-open-issues`; not merged yet.

The app keeps the SQLModel state database and replayable history database separate, each with its own explicit version-1 schema marker. The state store now migrates a unique ACK identity index and run-integrity triggers without deleting existing rows; duplicate legacy ACK identities fail migration into a visible degraded health state. Run-linked observations, commands, decisions, transitions, incidents and acknowledgments are preserved. A new site run now rotates the primary run ID as well as history identity.

Every site command records a UUID that is also returned in its receipt. The next durable decision references that command ID. Command payloads contain normalized room/session details, never raw RFID UIDs. ACK identity is `(run, device boot, sequence, session)`; duplicate ACKs return success without an additional ACK row, event, or state revision. Physical ACKs remain rejected until the physical command/session boundary is provisioned, so simulated acknowledgments never confirm GPIO state. Database failures are surfaced by `/api/v1/health` and ACK persistence errors return 503.

Both SQLite stores expose online backup methods. A backup is replaced into place only after SQLite integrity and referential/orphan checks succeed. The lifecycle tests reopen the backups and verify their retained rows. History retention and cursor gaps remain covered by the existing history tests.

Verification on 2026-10-10:

- `PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests -q --tb=short` — **157 passed**.
- `npm run build` — passed; existing large-bundle warning remains.
- `npm run test:contract` — passed, including updated health and command-receipt schema.
- `git diff --check` — passed.

`npm run test:history` — **4 passed** after installing the exact lockfile dependencies. No physical board/ACK test was performed. Backups are explicit local operations, not scheduled; SQLite remains a single-process authority and is not a multi-worker lock.
