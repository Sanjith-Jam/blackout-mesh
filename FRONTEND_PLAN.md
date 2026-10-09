# FRONTEND IMPLEMENTATION PLAN

*(Extracted exactly from PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md)*

## 13. Frontend control-room specification

### 13.1 Single-screen layout
- **Top bar:** Blackout Mesh / mode `LIVE_SIMULATION` / incident severity / synthetic-vs-radio provenance / connection indicators.
- **KPI row:** available source kW, requested kW, served kW, shed kW, essential loads served / total requested (including disconnected loads), gateway peers online.
- **Center left:** interactive single-line graph (source, feeder edges, buses, colored loads), legend distinguishing *simulated electric status* and *physical peer connectivity*.
- **Center right:** current incident, ranked hypotheses, missing evidence, uncertainty, chosen action, violated/infeasible constraints.
- **Bottom:** event timeline + telemetry charts + hardware ACK panel; switches for reset/scenario/injection/pause/auto/manual.
- **Tabs:** `Control Room`, `Incidents & Replay`, `FaultLab Evaluation`, `Hardware Health`, `Architecture/About`.

### 13.2 UI behaviors
- Use shadcn `Card`, `Badge`, `Alert`, `Tabs`, `Table`, `Dialog`, `Sheet`, `Tooltip`, `Sonner`.
- React Flow custom node types `sourceNode`, `busNode`, `loadNode`; edge stroke red broken/faulted, amber degraded, grey open, green served; **do not show a light glowing across an unreachable feeder**.
- ECharts: capacity demand/served timeline, per-bus `v_pu` with legend **SIMULATED**, fault score, action stage chart. Plot real ESP-NOW RTT and ACK success separately.
- Disabled/stale values become muted and timestamped; WebSocket reconnect first reloads `/api/state` to prevent out-of-order rendering.
- Hardware visual never changes to â€œACKEDâ€ before actual firmware ACK; simulation action may be â€œAPPLIED_SIMULATIONâ€ first.
- Evidence chips on every value: `SIMULATED`, `DERIVED_SIMULATION`, `EMULATED_INPUT`, `RADIO_TELEMETRY`, `PHYSICAL_INDICATOR`; never make *radio online* synonymous with *electric healthy*.
- Incident UX: â€œWhat happened?â€, â€œWhy?â€, â€œWhat did the controller do?â€, â€œWhat couldnâ€™t it know?â€, â€œWhat if greedy control was used?â€

### 13.3 Engineering speed
Start from a Vite/shadcn admin shell; **custom React Flow graph is the product center**, not decorative graphics. Include local empty/error/loading states. Use mock typed JSON snapshot provided by hour 1; switch transport to backend by hour 4. Build with `pnpm build` offline ahead of final demo. Require keyboard operation, visible focus, text/icons alongside color, readable contrast, local assets and reduced motion. Include a service-table alternative, last-update ages and loading/error/empty states. Keep the decision panel legible at 1366Ã—768; secondary history/charts belong in supporting tabs.


