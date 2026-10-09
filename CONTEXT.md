# Blackout Mesh — implementation context

Updated 2026-10-09. Planning only; targets are not measured results.

## Authority

Follow [unified implementation plan v1.1](PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md) and [AGENTS.md](AGENTS.md). The plan merges the newer seven-load blueprint with earlier reliability and validation requirements. Active tasks have no team-role allocations.

## Confirmed scope

- Open-ended hackathon; approximately 24 hours and ₹1,500 spending ceiling.
- Seven loads, 84 kW requested, 100 kW normal and 52/55 kW shortage examples; exact 128-mask oracle. Earlier six-load example is a separate 64-mask regression.
- React/TypeScript/Vite frontend, Python/FastAPI state authority, NetworkX/NumPy, OR-Tools, SQLite and ESP32/ESP-NOW as specified in the plan.
- Simulated power and observations, real radio/LED feedback. No mains switching, backup supply or implemented multi-hop mesh claim.
- Inventory includes 2–3 ESP32 boards and basic prototyping parts; working counts and variants need inspection. No owned potentiometer confirmed. Do not buy hardware by default.
- Code reuse is authorized; verify upstream licenses and preserve required notices when incorporating code. Research recommendations remain in local-only archives.
- Graphify and Security Auditor are installed for explicit on-demand use only.

## Validation and next action

Plan review checked allocation arithmetic, packet field widths, links and unchanged local reuse recommendations. No application, solver, firmware or hardware execution was validated.

Inspect existing workspace code and exact boards/toolchain before starting. Execute component dependencies and delivery gates in plan §14–15; establish the snapshot contract and first vertical slice. Update this file and README with commands and actual results as implementation progresses.

Historical plans and review records are outside the repository. The inherited blueprint reference was not independently available; do not treat it as separately verified evidence.
