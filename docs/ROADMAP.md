# Roadmap

Remaining work, ordered by what it adds to the demo and the evidence. Each item says what to build and how we will know it works. Sizes are rough: S under half a day, M about a day, L several days.

## Now (before judging)

1. **Live fault buttons on `/hospital` (S).** The buttons still call isolated rehearsal fixtures. Point them at the persistent `inject_fault` / `clear_fault` command so a fault changes the live hospital, the city map and history together. Done when a stuck-sensor injection shows on `/demo` and in the history timeline in the same revision.
2. **Judge mode (M).** One button that plays a fixed script with captions: request rooms → 6 kW shortage → feeder A trip → stuck sensor → repair → staged recovery. Use a deterministic replay file so ML states are the same every run. Done when two runs produce identical revisions and screenshots.
3. **Physical acceptance, B5 (M, needs both boards).** Flash, enroll three cards, pair A↔B, run the test table in `ESP32_A_CONNECTION_GUIDE.md`, log results in the repo and record a 90-second video. Show measured command→ACK latency on the boards panel.
4. **One-command launch (S).** Serve the built frontend from FastAPI and add `scripts/demo.sh` so the demo runs offline from one terminal.

## Next (makes the ML and allocation stronger)

5. **Appliance-level campus allocation (M).** The campus allocator still switches whole rooms (L3–L5), which is why even perfect occupancy adds under a point in the benchmark. Allocate the 19 equipment leaves directly with a per-feeder knapsack (integer watts, exact and polynomial), keep protected minima as hard constraints, then rerun the ablation. Done when the benchmark reports leaf-level results and the 64-plan path is kept only as a cross-check.
6. **Live room sensor (M).** Add a `LIVE_SENSOR` observation source and route it to the classroom view. Optional CO₂ sensor on board A. Add what-if sliders on `/classrooms` for CO₂ and temperature.
7. **Campus room data (L).** Collect two or three labelled sessions in real rooms, evaluate the frozen model on them and report separately from the UCI proxy.
8. **Wider stuck-sensor coverage (S).** Extend the frozen-reading rule to temperature and output voltage, then generate a fresh held-out diagnosis set (the current one has been opened).

## Later (product depth)

9. **Outage cost model (M).** Attach a configurable value per load tier so the benchmark can report avoided critical-load hours and an indicative cost, clearly labelled as modelled.
10. **Control-room theme (S).** A dark, low-glare variant that follows high-performance HMI practice: neutral greys at rest, saturated colour only for abnormal states.
11. **Scale path (M).** Benchmark the knapsack allocator from item 5 at 50, 100 and 500 loads and publish timings.
12. **Bundle size (S).** Split the 1.8 MB JavaScript bundle by route.
13. **Crash-safe history (M).** Make input-to-decision history writes atomic so a crash mid-transition cannot leave a partial record.
14. **Access control (M).** If the demo is ever exposed beyond localhost, add authentication for policy and simulation endpoints.
