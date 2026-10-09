# Blackout Mesh

Keep critical services first when available power falls, and show when evidence is insufficient.

A hackathon prototype combining a simulated campus power network, explainable allocation and real ESP32 radio/LED feedback. “Mesh” is a working name; multi-hop routing is outside scope.

## Project documents

- [Implementation plan](PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md): authoritative scope, architecture, contracts, delivery gates and acceptance checks.
- [Agent instructions](AGENTS.md): implementation workflow and invariants.
- [Context](CONTEXT.md): project status and next action.

## Status

Planning only. Application code, firmware and prototype tests have not been implemented in this repository. No build or run commands exist yet.

The main demo requests 84 kW across seven services, starts at 100 kW and drops to 52/55 kW. Electrical values are simulated; physical LEDs indicate independently acknowledged radio commands. The earlier six-load example remains a separate regression fixture.

Review notes, reuse research, notices drafts and historical plans are maintained locally outside this repository. Preserve applicable third-party license notices whenever code is incorporated.
