# Design Specification: BM-17 Simultaneous Faults, Hypothesis Ranking & Diagnostic Abstention

**Issue**: [#19 Support simultaneous faults, hypothesis ranking and diagnostic abstention](https://github.com/Sanjith-Jam/blackout-mesh/issues/19)  
**Plan ID**: BM-17  
**Date**: 2026-10-10  
**Status**: Approved Design  

---

## 1. Context and Problem Statement

The repository baseline prior to this work relied on two disparate, naive fault diagnosis implementations:

1. **Hospital Waterfall (`backend/app/visualizers.py:diagnose`)**:
   Uses a rigid `if-elif-else` waterfall.
   - If overload ($I > 1.1 \times I_{\text{rated}}$) occurs concurrently with cooling failure ($T \ge 80^\circ\text{C}$ and `cooling_ok = False`), the waterfall terminates on the overload check, completely masking cooling breakdown.
   - Only a single diagnosis code/string is produced per transformer.
   - Any single `None` reading causes total diagnostic abstention (`UNKNOWN`), discarding valid evidence across other sensors.
   - Sensor contradictions (e.g. current without voltage) are ignored or incorrectly diagnosed.
   - Severity and confidence are conflated into a single label.

2. **Campus Oracle Access (`backend/app/core/state.py:compute_fault_diagnosis`)**:
   Directly inspects simulator truth (`self.source_capacity_w` and `self.feeder_available`), violating Invariant 2 (*"Diagnosis/allocation read only observations, configured demand and policy — never scenario labels or simulator truth"*). Messages are merely concatenated strings.

This design introduces a modular, evidence-based diagnostic subsystem (`backend/app/diagnostics/`) that supports simultaneous fault coexistence, transparent heuristic ranking, explicit diagnostic abstention, and shared-cause attribution without double-counting.

---

## 2. Architecture & Data Model

### 2.1 Module Layout
```
backend/app/diagnostics/
├── __init__.py         # Public exports (diagnose_transformer, evaluate_telemetry, models)
├── models.py           # Pydantic schemas: Severity, Sufficiency, DiagnosticHypothesis, DiagnosticAbstention, DiagnosisResult
├── rules.py            # Independent rule evaluations (Overload, CoolingFailure, ThermalStress, UpstreamLoss, BranchInterrupted)
├── engine.py           # Contradiction check, rule execution, shared-cause attribution, ranking, and backwards-compatible projection
```

### 2.2 Core Schemas (`models.py`)

```python
from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NORMAL = "normal"
    UNKNOWN = "unknown"

class Sufficiency(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"

class DiagnosticHypothesis(BaseModel):
    id: str                                    # Unique hypothesis key (e.g. "TX2:COOLING_FAILURE")
    code: str                                  # "OVERLOAD", "COOLING_FAILURE", "THERMAL_STRESS", "UPSTREAM_LOSS", "BRANCH_INTERRUPTED"
    asset_id: str                              # Asset identifier (e.g. "TX1", "TX2", "FEEDER_F1")
    cause: str                                 # Human-readable failure explanation
    severity: Severity                         # Operational severity tier
    evidence_score: float                      # Heuristic score in [0.0, 1.0] (uncalibrated, NOT probability)
    sufficiency: Sufficiency                   # Observation sufficiency level
    supporting_evidence: List[str]             # Specific sensor readings supporting hypothesis
    contradicting_evidence: List[str] = []     # Readings tempering or contesting hypothesis
    recommendation: str                        # Recommended operator action

class AbstentionReason(str, Enum):
    INSUFFICIENT_TELEMETRY = "INSUFFICIENT_TELEMETRY"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    INDISTINGUISHABLE_CAUSES = "INDISTINGUISHABLE_CAUSES"

class DiagnosticAbstention(BaseModel):
    asset_id: str
    reason: AbstentionReason
    details: str
    missing_sensors: List[str] = []
    contradictory_readings: List[str] = []
    indistinguishable_candidates: List[str] = []
    next_check_needed: str                     # Actionable instruction to resolve ambiguity

class DiagnosisResult(BaseModel):
    asset_id: str
    status: Literal["NORMAL", "FAULT_DETECTED", "ABSTAINED"]
    hypotheses: List[DiagnosticHypothesis] = []
    abstention: Optional[DiagnosticAbstention] = None
    # Backwards-compatible projection for existing clients:
    code: str                                  # Top hypothesis code, "NORMAL", or "UNKNOWN"
    cause: str
    severity: str
    evidence: List[str]
    recommendation: str
```

---

## 3. Independent Rule Evaluation & Hypothesis Generation

### 3.1 Rule Specifications
Each rule inspects only available sensor observations and configured ratings:

1. **`OverloadRule`**:
   - Condition: $I > 1.1 \times I_{\text{rated}}$.
   - Severity: `HIGH`.
   - Score: Heuristic scale $0.75 + 0.25 \times \min(1.0, \frac{I - 1.1 I_{\text{rated}}}{0.5 I_{\text{rated}}})$.
   - Evidence: Current value vs. 110% threshold.

2. **`CoolingFailureRule`**:
   - Condition: $T \ge 80.0^\circ\text{C}$ and `cooling_ok is False`.
   - Severity: `HIGH`.
   - Score: $0.90$.
   - Evidence: Elevated temperature accompanied by reported cooling system failure.

3. **`ThermalStressRule`**:
   - Condition: $T \ge 80.0^\circ\text{C}$ and `cooling_ok is not False`.
   - Severity: `MEDIUM`.
   - Score: $0.70$.
   - Evidence: Elevated temperature under operational or unmonitored cooling.

4. **`UpstreamLossRule`**:
   - Condition: $V_{\text{in}} < 180.0\text{V}$ and $V_{\text{out}} < 100.0\text{V}$.
   - Severity: `CRITICAL`.
   - Score: $0.95$.
   - Evidence: Input and output voltages depressed below minimum operating thresholds.

5. **`BranchInterruptionRule`**:
   - Condition: $V_{\text{in}} \ge 180.0\text{V}$, $V_{\text{out}} < 100.0\text{V}$, and $I \le 1.0\text{A}$.
   - Severity: `HIGH`.
   - Score: $0.85$.
   - Evidence: Normal input voltage but collapsed secondary output with negligible load current.

### 3.2 Simultaneous Coexistence
Rules are executed concurrently across the observation envelope. If both `OverloadRule` and `CoolingFailureRule` match, both are appended to `hypotheses`.

### 3.3 Shared-Cause Attribution & Non-Double-Counting
When both electrical overload ($I > 1.1 I_{\text{rated}}$) and thermal elevation ($T \ge 80^\circ\text{C}$) are present:
- The system annotates the shared interaction: *"Elevated loading contributes to coil $I^2R$ thermal dissipation, compounding cooling stress."*
- Thermal elevation is not double-counted as an independent root electrical source failure.

### 3.4 Hypothesis Ranking
Hypotheses are sorted deterministically:
1. Primary key: Severity tier (`CRITICAL` (4) > `HIGH` (3) > `MEDIUM` (2) > `LOW` (1)).
2. Secondary key: `evidence_score` descending.

---

## 4. Contradiction Detection & Diagnostic Abstention

Before hypothesis generation, observations are checked for physical anomalies and observational limits:

1. **`CONTRADICTORY_EVIDENCE`**:
   - Condition: $V_{\text{in}} < 30.0\text{V}$ and $V_{\text{out}} < 30.0\text{V}$ while $I > 10.0\text{A}$ (current flowing through an unenergized transformer without backfeed).
   - Condition: $T < -30.0^\circ\text{C}$ or $T > 250.0^\circ\text{C}$ (out-of-range thermal reading indicating failed thermocouple).
   - Action: `status = "ABSTAINED"`, `reason = CONTRADICTORY_EVIDENCE`, `next_check_needed = "Verify calibration of current transducers and voltage instrumentation"`.

2. **`INSUFFICIENT_TELEMETRY`**:
   - Condition: Key sensor telemetry is absent (`None`) and no other supported hypotheses can be formed.
   - Scoped evaluation: If current $I$ is `None`, thermal/cooling rules still evaluate. If temperature is $92^\circ\text{C}$ and cooling failed, `COOLING_FAILURE` is diagnosed despite missing current.
   - Action: If no hypotheses can be established due to missing telemetry, `status = "ABSTAINED"`, `reason = INSUFFICIENT_TELEMETRY`, `next_check_needed = "Restore sensor telemetry for: <missing_sensors>"`.

3. **`INDISTINGUISHABLE_CAUSES`**:
   - Condition: $V_{\text{in}} \ge 180.0\text{V}$, $V_{\text{out}} = 0.0\text{V}$, $I = 0.0\text{A}$ without local breaker telemetry.
   - Action: `status = "ABSTAINED"`, `reason = INDISTINGUISHABLE_CAUSES`, `indistinguishable_candidates = ["SECONDARY_BREAKER_OPEN", "PRIMARY_FUSE_BLOWN", "BUSBAR_FAULT"]`, `next_check_needed = "Inspect physical transformer secondary breaker trip flag and fuse continuity"`.

---

## 5. API and UI Integration

### 5.1 Shared Contract
Per repo invariants (*"Snapshot/API schema changes touch Python models, TypeScript types, fixtures and serial translation in one commit"*):

- **Backend (`backend/app/visualizers.py`)**:
  - `diagnose(...)` wraps `diagnose_transformer(...)`.
  - `hospital_snapshot(...)` assigns `DiagnosisResult` to each transformer's `diagnosis` attribute.
  - Legacy fields (`code`, `severity`, `cause`, `evidence`, `recommendation`) remain available at the top level of `transformer.diagnosis`.
- **Backend (`backend/app/core/state.py`)**:
  - `compute_fault_diagnosis()` structures campus faults into candidate hypotheses rather than plain string concatenation.
- **Frontend (`frontend/src/types.ts`)**:
  - Define `DiagnosticHypothesis`, `DiagnosticAbstention`, and update `HospitalDemoDiagnosis`.
- **Frontend (`frontend/src/pages/HospitalDemo.tsx`)**:
  - Render multiple hypothesis tags when multiple faults exist.
  - Display explicit abstention warning box with `next_check_needed`.
  - Label heuristic scores explicitly as *"Heuristic score (uncalibrated)"*.

---

## 6. Verification and Acceptance Matrix

### 6.1 Test Suites
1. **`backend/tests/test_diagnostics.py`**:
   - Simultaneous faults: Overload + Cooling Failure co-occur in `hypotheses`.
   - Contradiction: Zero voltage with heavy current yields `CONTRADICTORY_EVIDENCE`.
   - Scoped missing data: Missing current still allows cooling failure diagnosis.
   - Total missing data: All `None` yields `INSUFFICIENT_TELEMETRY`.
   - Ambiguity: Normal input with zero output yields `INDISTINGUISHABLE_CAUSES`.
   - Ranking: Critical upstream loss ranks above medium thermal stress.
   - Backward compatibility: Legacy fields match expected values.
2. **`backend/tests/test_visualizers.py`**:
   - Verify hospital visualizer endpoint returns populated hypotheses.
3. **Frontend Production Build**:
   - `npm run build` passes with zero type errors.
