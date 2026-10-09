# Lab activity classification and power priority — required plan revision

Updated 2026-10-09. This revision is required by the user and takes precedence over the unified v1.1 plan's optional-ML wording, seven-load primary example, B/C hardware split and manually selected RFID priority profiles. General electrical guards, fault diagnosis, radio/session validation, restoration and honest provenance requirements still apply. Planning only: no classifier has been trained.

## 1. Decision

Use a CPU-trained **RandomForestClassifier** as the first candidate for binary lab activity estimation. Its inputs are small tabular observations, not video. Compare against a timetable-only rule, a recent-activity rule and logistic regression. Final model choice depends on validation results; no model can be called best before data and evaluation exist. JEPA-style image/video representation models are not justified for the current sensor inventory and time box.

ML is now a required project component, separate from optional Isolation Forest fault novelty detection. A trained model estimates activity; a deterministic policy assigns priority; the constrained allocator selects feasible loads. The classifier does not output a power mask or override safety constraints. A failed or unavailable model uses a visibly labeled rules fallback; that fallback alone does not fulfill the trained-model requirement.

## 2. Nine-load primary catalog

Split only the original 16 kW laboratory into three independently controlled circuits. Retain the other six services, source 100 kW, feeder A→B limit 60 kW and A→C limit 55 kW. Total configured demand remains 84 kW.

| Bit | ID | Service | Demand W | Bus | Base policy |
|---:|---|---|---:|---|---|
| 0 | L_CLINIC | Clinic | 18,000 | B | Fixed T0 |
| 1 | L_EMERG | Emergency lights | 8,000 | A | Fixed T0 |
| 2 | L_SERVER | Server/network | 12,000 | A | Fixed T1 |
| 3 | L_LAB_A | Lab A | 6,000 | C | Activity-aware |
| 4 | L_LAB_B | Lab B | 6,000 | C | Activity-aware |
| 5 | L_LAB_C | Lab C | 4,000 | C | Activity-aware |
| 6 | L_HOSTEL | Hostel/shelter | 14,000 | B | General T2 |
| 7 | L_CLASSROOM | Classroom | 10,000 | C | General T3 |
| 8 | L_AMENITIES | Amenities | 6,000 | A | General T3 |

Primary exact oracle: **512 masks**; valid indicator mask `0x0000..0x01ff`; all nine bits = 511. Keep the proposed explicit 26-byte radio frame, but use application version 2 for the expanded mask and reject legacy three-bit peers. Update Python/firmware/serial fixtures together; never truncate to eight bits. The old seven-load 128-mask and six-load 64-mask examples remain named regression fixtures with their own catalogs, not primary outputs. Never reuse a historical bit mask under the new catalog without translation.

ESP32 A: RFID reader, four buttons, USB gateway, optional servo gauge. ESP32 B: nine separate load LEDs plus a link-status LED. No third ESP32, Arduino board or display is needed. Verify that the actual dev board exposes enough safe output pins before wiring; otherwise keep clinic/emergency/server virtual and prioritize physical LEDs for the three labs and general services. Publish that reduced physical coverage explicitly.

## 3. What the classifier predicts

Train labels: `ACTIVE` / `INACTIVE` for a defined lab session/window. `UNKNOWN` is a pipeline abstention state, not a third fabricated training label. Define active operationally: an independently documented teaching, experiment or supervised work session is in progress. Booked is not automatically active; presence alone is not proof that equipment is in use. Background/always-on safety equipment is excluded from the shed-capable lab circuit.

Required output per lab: `activity_state`, raw `p_active`, last valid observation/inference time, feature freshness/quality, source tags, model version and threshold version. Raw forest scores are not calibrated probabilities until calibration has been independently checked. UI can show a model score and must show UNKNOWN/stale distinctly.

Starting thresholds, to tune on validation data only: ACTIVE if score ≥0.8 for 5 s; INACTIVE if score ≤0.2 for 15 s; otherwise UNKNOWN. Evaluate once per second from causal windows. Missing/stale required features or invalid model output produce UNKNOWN immediately; do not turn missing observations into zeros or inactivity. Record simulated versus host clocks explicitly; radio health remains host-monotonic.

## 4. Inputs realistically available

| Feature | Source in this prototype | Limit |
|---|---|---|
| Timetable active flag and minutes from booked start/end | Configured/simulated schedule | Booking can be wrong; never used as ground truth label |
| Recent session-start/end request and age | RFID-selected lab + button event, tagged EMULATED_INPUT | Operator input is fallible evidence, not proof of occupancy |
| Recent workstation/experiment activity count and age | Simulated independent activity reports | No physical PC network monitoring is currently installed |
| Presence fraction and validity over a trailing window | Simulated per-lab presence; optional ultrasonic tabletop input for the selected lab | One ultrasonic sensor cannot observe three real rooms; a reflector/hand is a demo observation, not a person count |
| Observation ages, missing indicators and recent changes | Derived from permitted timestamped observations | Compute causally; no future windows |

Do not feed ground-truth occupancy, scenario ID, future samples, final priority, allocator mask, current served-power state or card UID into the model. UID only identifies which lab an event concerns. Excluding served-power state prevents a shed lab being falsely classified inactive merely because its circuit is off. Occupancy/activity reports are modeled as independently available evidence; when they disappear, abstain.

## 5. Data, training and evaluation

1. Freeze feature/label definitions and sampling cadence before generating data. Keep hidden occupancy/session truth separate from the observer. Generate independently noisy schedules, activity observations, missed/late requests, dropouts, idle sessions, active-unbooked labs and booked-but-empty labs. Do not manufacture labels by directly thresholding a model input.
2. Start with 30 independent synthetic session/day groups per lab (90 groups), balanced coverage of active/inactive periods and edge cases. These are prototype synthetic records, not real-campus training data or proof of deployment accuracy.
3. Split whole groups: first 18 per lab for training, next 6 validation, last 6 untouched test. Keep overlapping windows inside their original group; embargo at least one longest feature window across adjacent temporal splits. If later real lab sessions exist, split by session/day and reserve a lab/day generalization check. Never randomly split adjacent rows.
4. Impute/encode through a pipeline fit only on training data. Keep explicit missing indicators, feature order and unit checks. Start with 100 trees, max depth 6, minimum leaf 5, balanced class weights and fixed seed; these are initial settings, not optimized values. Tune a small bounded set using validation groups only.
5. Compare RF with simple rules and logistic regression. Select thresholds for low false-INACTIVE rate on actual ACTIVE windows, report abstention/coverage, then freeze model/config before the test set. No universal accuracy target is guaranteed by the plan.
6. Report macro-F1, active recall, false-INACTIVE count/rate, confusion matrix, UNKNOWN rate, coverage, class support, per-lab/session outcomes and inference latency. Also compare final allocations under fixed priority, rules-based activity and model-based activity using identical capacity/feeder/transition constraints.
7. Data/model generation may run offline. Store dataset manifest, group split, seed, feature schema, training command, dependencies, model hash and measured metrics. Load only the trusted local model artifact generated by this project; do not deserialize arbitrary uploaded pickle/joblib files.

If real labeled data are unavailable, say “trained and evaluated on synthetic lab-session data.” RFID/ultrasonic bench demonstrations do not validate occupancy detection in a real lab. If RF does not beat the baseline, show that result and use the labeled safe fallback; do not conceal it or claim model-driven improvement.

## 6. Priority and allocation policy

Clinic/emergency T0 and server T1 retain fixed precedence. For the remaining eligible services, maximize lexicographically:

1. T0 served count, T0 importance (clinic 2/emergency 1), T1 count.
2. Served ACTIVE lab count.
3. Served UNKNOWN lab count.
4. Served general T2 count (hostel).
5. Served general T3 count (classroom and amenities).
6. Negative watts assigned to confirmed INACTIVE lab circuits.
7. Negative switching count, then negative global mask.

This deliberately lowers known unused lab circuits without allowing them to outrank essential services. UNKNOWN receives conservative intermediate priority; it is not treated as confidently empty. A live lab is not promoted above clinic/emergency/server merely because a model score is high. Safety/always-on lab equipment must be modeled separately if present; the prototype only controls hypothetical nonessential lab circuits through LEDs.

Apply classification changes only after the specified stability windows. Protective shedding remains immediate. Every proposed mask still passes an independent capacity/feeder/reachability/freshness/revision/lockout validator, including retained-ON demand. Reconnection still needs 5 s stable fresh capacity, 3 s minimum OFF dwell, one new ON per second, with OFF transitions applied first. Every baseline receives identical transition constraints and electrical observations.

Illustrative arithmetic with all three labs ACTIVE and initial all-ON state, no additional locks: at 55 kW mask 63 serves clinic/emergency/server plus all labs =54 kW; at 52 kW mask 31 serves clinic/emergency/server plus labs A/B =50 kW under the stated tie-break. These replace the primary seven-load mask 15/23 examples; historical fixtures retain their own expected outputs. Do not hard-code these masks in live firmware.

## 7. New RFID/judge interaction

Three RFID cards identify **Lab A / Lab B / Lab C**. Scanning selects the lab shown on the laptop and produces a selection event, not a priority assignment or a prediction. Buttons:

- SESSION START: timestamped observed start request for the selected lab.
- SESSION END: timestamped observed end request for the selected lab.
- BLACKOUT: set simulated supply to 55 kW; optional software control demonstrates 52 kW.
- RESTORE: restore supply and close injected feeder fault; hold for two seconds to reset the scene with explicit UI confirmation state and new session. Short press fires on release; a completed long hold must not also emit RESTORE.

Unknown cards do not change state. Coalesce repeated scans until removal/re-presentation. If the host is unavailable, show rejection/stale; no hidden queued future action. These events update causal model features. Live classifier output and optimizer decisions must occur before LEDs change. A direct card→fixed-mask sequence is SCRIPTED EXHIBIT, not ML inference.

Judge story: select a lab, begin a session, watch activity classification update, reduce supply, see active labs receive preference while unused circuits are shed; end a session and watch the status change after the confidence/dwell rule. Demonstrate an ambiguous/missing report as UNKNOWN and a broken feeder as a hard constraint. On the laptop show per-lab evidence, prediction, priority, served/shed reason and hardware ACK status as separate fields. Optional servo indicates committed simulated source budget only.

## 8. Implementation phases and dependencies

| Phase | Tasks | Exit evidence |
|---|---|---|
| M0: schema/catalog (45 min) | Nine-load config; feature/label schema; causal observation channel; enum/mask revision | Validated fixtures; old catalogs kept separate |
| M1: data and baselines (60–90 min) | Independent synthetic generator; group split; timetable/activity rules | Dataset/split manifest, labeled baseline report |
| M2: trained model (60–90 min) | Fit RF and logistic regression; validation thresholds; freeze artifact | Trusted artifact, feature/config versions, measured validation outputs |
| M3: runtime and policy (60–90 min) | 1 Hz bounded inference; abstention/stability; nine-load objective/oracle; queue/revision integration | Predictions visibly enter allocator; all 512 masks independently checked for chosen fixtures |
| M4: hardware/UI (60–90 min) | Lab-ID cards and four controls; nine LEDs or declared reduced coverage; snapshots/reasons | Real input → inference → allocation → matching GPIO ACK |
| M5: held-out report/rehearsal (60 min) | Untouched grouped test; no-leakage and dropout cases; fixed/rule/model policy comparison | Metrics with denominators/failures, honest synthetic label and three demo repetitions |

Do not defer the trained classifier behind servo/ultrasonic/presentation polish. Preserve a readable rules fallback for invalid/missing model, but show which path ran. The time allocations are targets, not completed results.

## 9. Required checks and artifacts

- Features never access evaluator truth, future rows or post-shedding power status.
- Training/validation/test session groups are disjoint; preprocessing is train-fit only.
- Model errors, missing input and stale evidence yield UNKNOWN/rules fallback visibly.
- Known active labs are not demoted because a radio display peer failed or their circuit was shed.
- Critical tiers and all electrical guards dominate occupancy benefits.
- Exact/CP-SAT objective agreement across the nine-load catalog and separate old fixtures; no mixed mask identities.
- Record training data source, feature/threshold/model/config versions and final test results; no placeholder accuracy.

Planned artifacts: `backend/app/activity/` for features/inference, `backend/scripts/train_activity.py`, trusted `backend/models/` artifact/manifest, dataset split/metrics report, typed lab-state snapshots, input/radio fixtures and updated hardware pin map. Create only as each component is implemented; no code/artifact currently exists.

## Sources for model selection

- [scikit-learn RandomForestClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html): classifier, class weights and score interface.
- [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html): future-to-past leakage concern; this plan additionally groups complete sessions and uses a temporal embargo.
- [Meta I-JEPA research](https://ai.meta.com/research/publications/self-supervised-learning-from-images-with-a-joint-embedding-predictive-architecture/): image representation learning; useful if a justified vision scope/data source is later requested, not the default for this inventory.
