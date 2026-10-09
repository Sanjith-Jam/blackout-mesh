# Diagnosis benchmark protocol (#18) — `diag-bench-protocol-1`

Written before any evaluation. Changing anything below creates a new protocol version, and any set evaluated under the old version becomes a development set.

## Process label

**Developer-held-out, not fully blind.** The project has no independent custodian, so the same developers generate fixtures and write detectors. Held-out fixtures are still generated from parameter regimes no detector was tuned on, and their truth stays sealed (see below).

## Assets and observations

Three transformers TX1–TX3 (rated 100 A) share one upstream supply. Each step emits one observation envelope per asset and quantity: `current_a`, `temperature_c`, `input_voltage_v`, `output_voltage_v`, `cooling_ok`. Steps are 0.25 s apart; a scenario has 32 steps. Envelopes carry asset, quantity, unit, value or null, observed time, sequence and quality. **No envelope or bundle field carries a scenario, family, fault or label.** Scenario IDs are opaque hashes.

## Fault families

| Family | Truth on the affected asset(s) | Expected detector output |
|---|---|---|
| `normal` | no fault | NORMAL |
| `demand_change` (distractor) | load rises within rating | NORMAL |
| `hot_ambient` (distractor/ambiguity) | high temperature, normal current, cooling OK | HIGH_TEMPERATURE (not COOLING_FAILURE / OVERLOAD) |
| `overload` | current above 110% of rating, temperature rising | OVERLOAD |
| `cooling_failure` | cooling failed, temperature high, current normal | COOLING_FAILURE |
| `overload_and_cooling` (simultaneous) | both | OVERLOAD or COOLING_FAILURE on the right asset |
| `upstream_loss` | all three inputs and outputs collapse | UPSTREAM_LOSS on every asset |
| `branch_interruption` | one asset's input/output collapse, others normal | BRANCH_INTERRUPTION on that asset only |
| `sensor_dropout` | one quantity becomes null | ABSTAINED on that asset |
| `stuck_sensor` | one quantity frozen at its last value while the true value moves | either the true fault or abstention; a confident NORMAL during a real fault is a safety violation |
| `delay_reorder` | some samples arrive late or out of order | the underlying truth (normal or overload) |
| `recovery_chatter` | fault toggles on and off every few steps | no INFERRED fault while truth is normal for ≥ 2 steps |

The fault onset is drawn per scenario; truth before onset is `normal`.

## Splits by parameter regime (never by rows of one trajectory)

| Split | Overload level | Hot temperature | Noise (σ current / temp) | Delay/reorder | Purpose |
|---|---|---|---|---|---|
| `dev` | 125–140% | 86–95 °C | 1 A / 0.5 °C | ≤ 1 step | develop and debug detectors |
| `calibration` | 116–124% | 82–85.9 °C | 3 A / 1.5 °C | ≤ 2 steps | tune thresholds; becomes development data once used |
| `heldout` | 110.5–115.5% and 141–170% | 80–81.9 °C and 95.1–110 °C | 5 A / 2.5 °C | ≤ 3 steps | final evaluation only |

The ranges are disjoint: no held-out parameter value occurs in development or calibration data.

Every family appears in every split. Seeds: dev 0–3, calibration 100–103, heldout 1000–1003 per family.

## Sealing

Observation bundles and truth files are separate files, each with a SHA-256 in `manifest.json`. The runner reads only observation bundles. While a detector runs, an audit hook fails the run if any truth file is opened. The evaluator joins predictions to truth afterwards. **Held-out truth is never evaluated without `--unseal`**, and unsealing appends a line to `UNSEALED.log`. Held-out results stay sealed until the multi-hypothesis diagnosis (#19) and allocation candidates are frozen. Any retuning after unsealing turns the held-out set into a development set and requires a new held-out set.

## Metrics (per family, with denominators)

- **Detection recall:** scenarios whose expected code is INFERRED on the right asset after onset / scenarios with a fault.
- **Precision:** correct INFERRED fault claims / all INFERRED fault claims (scenario-asset level).
- **False alarms:** asset-steps with an INFERRED fault while truth is normal (count and per-asset-step rate).
- **Time to detect:** steps from onset to the first correct INFERRED claim (median, max).
- **Location error:** scenarios where the fault is claimed on a non-faulty asset.
- **Abstention / coverage:** abstained asset-steps / all asset-steps; correct abstentions for `sensor_dropout`.
- **Safety violations:** asset-steps after onset + 2 confirmation steps where the detector reports INFERRED NORMAL on an asset with a real fault.

All misses and uncertain cases stay in the report.
