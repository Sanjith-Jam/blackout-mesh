# Simultaneous Fault Diagnosis, Hypothesis Ranking & Abstention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular, evidence-based diagnostic subsystem (`backend/app/diagnostics/`) that supports simultaneous fault coexistence, heuristic ranking, explicit diagnostic abstention, and shared-cause attribution across the hospital and campus visualizers.

**Architecture:** Independent diagnostic rule evaluators inspect observation envelopes without oracle access to simulator truth. Contradiction checks and missing data boundaries yield explicit abstentions with required inspections (`next_check_needed`). Candidate hypotheses are ranked deterministically by severity and uncalibrated heuristic evidence score. Contracts are shared across Python and TypeScript in atomic steps.

**Tech Stack:** Python 3.14 (FastAPI, Pydantic v2, Pytest), TypeScript (React, Vite).

**Spec:** `docs/superpowers/specs/2026-10-10-simultaneous-fault-diagnosis-design.md`

## Global Constraints

- Power is integer watts; voltage is integer or float volts; current is float amperes; temperature is float Celsius.
- Telemetry reads only observation envelopes and configured equipment ratings/topology — never simulator ground-truth flags.
- Heuristic evidence scores must be labeled as uncalibrated scores in $[0.0, 1.0]$, never pseudo-probabilities.
- Missing data is `None`/`unknown`, never zero.
- Backward compatibility: Existing top-level `code`, `cause`, `severity`, `evidence`, and `recommendation` fields must remain populated in `DiagnosisResult`.
- Shared contract changes touch Python schemas, TypeScript types, and tests in coordinated commits.

## Review Focus

1. *Powerless Current Contradiction*: $V_{\text{in}} < 30\text{V}$, $V_{\text{out}} < 30\text{V}$, but $I > 10\text{A}$ must yield `CONTRADICTORY_EVIDENCE` abstention instead of `OVERLOAD`.
2. *Simultaneous Overload + Cooling Failure*: $I = 130\text{A}$, $T = 92^\circ\text{C}$, `cooling_ok = False` must yield BOTH `OVERLOAD` and `COOLING_FAILURE` hypotheses without one masking the other.
3. *Scoped Telemetry Dropout*: Current $I$ is `None`, but $T = 91^\circ\text{C}$ and `cooling_ok = False` must successfully diagnose `COOLING_FAILURE` rather than bailing out to generic `UNKNOWN`.
4. *Observational Ambiguity*: $V_{\text{in}} = 230\text{V}$, $V_{\text{out}} = 0\text{V}$, $I = 0\text{A}$ must yield `INDISTINGUISHABLE_CAUSES` listing candidate possibilities and `next_check_needed`.
5. *Deterministic Ranking*: Higher severity ranks above lower severity regardless of evidence score (e.g. `CRITICAL` at 0.70 ranks ahead of `HIGH` at 0.95); within the same severity, higher `evidence_score` ranks first.

---

### Task 1: Diagnostic Models (`backend/app/diagnostics/models.py`)

**Files:**
- Create: `backend/app/diagnostics/__init__.py`
- Create: `backend/app/diagnostics/models.py`
- Test: `backend/tests/test_diagnostics.py`

**Interfaces:**
- Produces: `Severity`, `Sufficiency`, `DiagnosticHypothesis`, `AbstentionReason`, `DiagnosticAbstention`, `DiagnosisResult`

- [ ] **Step 1: Write the failing test for diagnostic data models**

```python
# backend/tests/test_diagnostics.py
import pytest
from app.diagnostics.models import (
    Severity,
    Sufficiency,
    DiagnosticHypothesis,
    AbstentionReason,
    DiagnosticAbstention,
    DiagnosisResult,
)

def test_diagnostic_models_instantiation():
    hypo = DiagnosticHypothesis(
        id="TX2:OVERLOAD",
        code="OVERLOAD",
        asset_id="TX2",
        cause="Current exceeds configured rating threshold",
        severity=Severity.HIGH,
        evidence_score=0.88,
        sufficiency=Sufficiency.SUFFICIENT,
        supporting_evidence=["Current 130.0 A; overload threshold 110.0 A."],
        contradicting_evidence=[],
        recommendation="Review connected demand and verify protection.",
    )
    assert hypo.code == "OVERLOAD"
    assert hypo.severity == Severity.HIGH
    assert hypo.evidence_score == 0.88

    abstention = DiagnosticAbstention(
        asset_id="TX1",
        reason=AbstentionReason.CONTRADICTORY_EVIDENCE,
        details="Current detected without voltage supply",
        contradictory_readings=["Input voltage 0.0 V", "Current 120.0 A"],
        next_check_needed="Verify current transducer and voltmeter calibration",
    )
    assert abstention.reason == AbstentionReason.CONTRADICTORY_EVIDENCE

    res = DiagnosisResult(
        asset_id="TX2",
        status="FAULT_DETECTED",
        hypotheses=[hypo],
        abstention=None,
        code=hypo.code,
        cause=hypo.cause,
        severity=hypo.severity.value,
        evidence=hypo.supporting_evidence,
        recommendation=hypo.recommendation,
    )
    assert res.status == "FAULT_DETECTED"
    assert len(res.hypotheses) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.diagnostics'`

- [ ] **Step 3: Implement diagnostic models**

```python
# backend/app/diagnostics/__init__.py
"""Modular telemetry-derived diagnosis subsystem."""

# backend/app/diagnostics/models.py
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
    id: str
    code: str
    asset_id: str
    cause: str
    severity: Severity
    evidence_score: float
    sufficiency: Sufficiency
    supporting_evidence: List[str]
    contradicting_evidence: List[str] = Field(default_factory=list)
    recommendation: str

class AbstentionReason(str, Enum):
    INSUFFICIENT_TELEMETRY = "INSUFFICIENT_TELEMETRY"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    INDISTINGUISHABLE_CAUSES = "INDISTINGUISHABLE_CAUSES"

class DiagnosticAbstention(BaseModel):
    asset_id: str
    reason: AbstentionReason
    details: str
    missing_sensors: List[str] = Field(default_factory=list)
    contradictory_readings: List[str] = Field(default_factory=list)
    indistinguishable_candidates: List[str] = Field(default_factory=list)
    next_check_needed: str

class DiagnosisResult(BaseModel):
    asset_id: str
    status: Literal["NORMAL", "FAULT_DETECTED", "ABSTAINED"]
    hypotheses: List[DiagnosticHypothesis] = Field(default_factory=list)
    abstention: Optional[DiagnosticAbstention] = None
    code: str
    cause: str
    severity: str
    evidence: List[str]
    recommendation: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/diagnostics/ backend/tests/test_diagnostics.py
git commit -m "diagnostics: add core schemas and data models"
```

---

### Task 2: Independent Rule Evaluator (`backend/app/diagnostics/rules.py`)

**Files:**
- Create: `backend/app/diagnostics/rules.py`
- Modify: `backend/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: `models.py` (`DiagnosticHypothesis`, `Severity`, `Sufficiency`)
- Produces: `evaluate_overload`, `evaluate_cooling`, `evaluate_thermal`, `evaluate_upstream_loss`, `evaluate_branch_interrupted`

- [ ] **Step 1: Write the failing tests for rule evaluators**

```python
# append to backend/tests/test_diagnostics.py
from app.diagnostics.rules import (
    evaluate_overload,
    evaluate_cooling,
    evaluate_thermal,
    evaluate_upstream_loss,
    evaluate_branch_interrupted,
)

def test_rule_evaluators_independent():
    # Overload
    hypo_ov = evaluate_overload("TX2", rated_current_a=100.0, current_a=130.0)
    assert hypo_ov is not None
    assert hypo_ov.code == "OVERLOAD"
    assert hypo_ov.severity == Severity.HIGH
    assert hypo_ov.evidence_score >= 0.75

    # Cooling failure
    hypo_cf = evaluate_cooling("TX2", temperature_c=91.0, cooling_ok=False)
    assert hypo_cf is not None
    assert hypo_cf.code == "COOLING_FAILURE"
    assert hypo_cf.severity == Severity.HIGH

    # Thermal stress when cooling operational
    hypo_th = evaluate_thermal("TX2", temperature_c=85.0, cooling_ok=True)
    assert hypo_th is not None
    assert hypo_th.code == "HIGH_TEMPERATURE"
    assert hypo_th.severity == Severity.MEDIUM

    # Upstream loss
    hypo_up = evaluate_upstream_loss("TX1", input_voltage_v=90.0, output_voltage_v=20.0)
    assert hypo_up is not None
    assert hypo_up.code == "UPSTREAM_LOSS"
    assert hypo_up.severity == Severity.CRITICAL

    # Branch interrupted
    hypo_br = evaluate_branch_interrupted("TX3", input_voltage_v=230.0, output_voltage_v=20.0, current_a=0.0)
    assert hypo_br is not None
    assert hypo_br.code == "BRANCH_INTERRUPTED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -k "test_rule_evaluators" -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.diagnostics.rules'`

- [ ] **Step 3: Implement rule evaluators**

```python
# backend/app/diagnostics/rules.py
from typing import Optional
from app.diagnostics.models import DiagnosticHypothesis, Severity, Sufficiency

def evaluate_overload(asset_id: str, rated_current_a: float, current_a: Optional[float]) -> Optional[DiagnosticHypothesis]:
    if current_a is None:
        return None
    threshold = rated_current_a * 1.1
    if current_a > threshold:
        margin = max(0.0, current_a - threshold)
        score = round(min(1.0, 0.75 + 0.25 * (margin / max(1.0, 0.5 * rated_current_a))), 2)
        return DiagnosticHypothesis(
            id=f"{asset_id}:OVERLOAD",
            code="OVERLOAD",
            asset_id=asset_id,
            cause="Current exceeds configured rating threshold",
            severity=Severity.HIGH,
            evidence_score=score,
            sufficiency=Sufficiency.SUFFICIENT,
            supporting_evidence=[f"Current {current_a:.1f} A exceeds overload threshold {threshold:.1f} A (110% of rating)."],
            recommendation="Review connected demand and verify with qualified protection equipment.",
        )
    return None

def evaluate_cooling(asset_id: str, temperature_c: Optional[float], cooling_ok: Optional[bool]) -> Optional[DiagnosticHypothesis]:
    if temperature_c is None or cooling_ok is None:
        return None
    if temperature_c >= 80.0 and not cooling_ok:
        return DiagnosticHypothesis(
            id=f"{asset_id}:COOLING_FAILURE",
            code="COOLING_FAILURE",
            asset_id=asset_id,
            cause="Elevated temperature with cooling reported failed",
            severity=Severity.HIGH,
            evidence_score=0.90,
            sufficiency=Sufficiency.SUFFICIENT,
            supporting_evidence=[
                f"Temperature {temperature_c:.1f} °C reaches hot threshold 80.0 °C.",
                "Cooling system status reported failed.",
            ],
            recommendation="Inspect cooling equipment and temperature using approved procedures.",
        )
    return None

def evaluate_thermal(asset_id: str, temperature_c: Optional[float], cooling_ok: Optional[bool]) -> Optional[DiagnosticHypothesis]:
    if temperature_c is None:
        return None
    if temperature_c >= 80.0 and cooling_ok is not False:
        return DiagnosticHypothesis(
            id=f"{asset_id}:HIGH_TEMPERATURE",
            code="HIGH_TEMPERATURE",
            asset_id=asset_id,
            cause="Elevated transformer temperature",
            severity=Severity.MEDIUM,
            evidence_score=0.70,
            sufficiency=Sufficiency.SUFFICIENT if cooling_ok is not None else Sufficiency.PARTIAL,
            supporting_evidence=[f"Temperature {temperature_c:.1f} °C reaches hot threshold 80.0 °C."],
            contradicting_evidence=["Cooling system reported operational."] if cooling_ok is True else [],
            recommendation="Check loading, ventilation and sensor readings.",
        )
    return None

def evaluate_upstream_loss(asset_id: str, input_voltage_v: Optional[float], output_voltage_v: Optional[float]) -> Optional[DiagnosticHypothesis]:
    if input_voltage_v is None or output_voltage_v is None:
        return None
    if input_voltage_v < 180.0 and output_voltage_v < 100.0:
        return DiagnosticHypothesis(
            id=f"{asset_id}:UPSTREAM_LOSS",
            code="UPSTREAM_LOSS",
            asset_id=asset_id,
            cause="Possible upstream supply loss",
            severity=Severity.CRITICAL,
            evidence_score=0.95,
            sufficiency=Sufficiency.SUFFICIENT,
            supporting_evidence=[
                f"Input voltage {input_voltage_v:.1f} V is below low-input threshold 180.0 V.",
                f"Output voltage {output_voltage_v:.1f} V is below de-energized threshold 100.0 V.",
            ],
            recommendation="Check the upstream supply and incoming connections.",
        )
    return None

def evaluate_branch_interrupted(asset_id: str, input_voltage_v: Optional[float], output_voltage_v: Optional[float], current_a: Optional[float]) -> Optional[DiagnosticHypothesis]:
    if input_voltage_v is None or output_voltage_v is None:
        return None
    if input_voltage_v >= 180.0 and output_voltage_v < 100.0 and (current_a is None or current_a <= 1.0):
        return DiagnosticHypothesis(
            id=f"{asset_id}:BRANCH_INTERRUPTED",
            code="BRANCH_INTERRUPTED",
            asset_id=asset_id,
            cause="Downstream branch interruption with normal upstream supply",
            severity=Severity.HIGH,
            evidence_score=0.85,
            sufficiency=Sufficiency.SUFFICIENT if current_a is not None else Sufficiency.PARTIAL,
            supporting_evidence=[
                f"Input voltage {input_voltage_v:.1f} V is normal (>= 180.0 V).",
                f"Output voltage {output_voltage_v:.1f} V is collapsed (< 100.0 V).",
            ],
            recommendation="Inspect branch isolation switch, fuses, and secondary circuit continuity.",
        )
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -k "test_rule_evaluators" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/diagnostics/rules.py backend/tests/test_diagnostics.py
git commit -m "diagnostics: implement independent rule evaluators"
```

---

### Task 3: Diagnostic Engine with Ranking, Contradiction & Abstention (`backend/app/diagnostics/engine.py`)

**Files:**
- Create: `backend/app/diagnostics/engine.py`
- Modify: `backend/app/diagnostics/__init__.py`
- Modify: `backend/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: `models.py`, `rules.py`
- Produces: `diagnose_transformer(rated_current_a, current_a, temperature_c, input_voltage_v, output_voltage_v, cooling_ok, asset_id="TX") -> DiagnosisResult`

- [ ] **Step 1: Write the failing tests for engine ranking, simultaneous faults, and abstentions**

```python
# append to backend/tests/test_diagnostics.py
from app.diagnostics.engine import diagnose_transformer

def test_simultaneous_faults_overload_and_cooling():
    res = diagnose_transformer(
        rated_current_a=100.0,
        current_a=130.0,
        temperature_c=91.0,
        input_voltage_v=230.0,
        output_voltage_v=218.0,
        cooling_ok=False,
        asset_id="TX2",
    )
    assert res.status == "FAULT_DETECTED"
    codes = [h.code for h in res.hypotheses]
    assert "OVERLOAD" in codes
    assert "COOLING_FAILURE" in codes
    assert len(res.hypotheses) >= 2
    # Check shared cause annotation
    assert any("compounds" in " ".join(h.supporting_evidence).lower() or "thermal" in " ".join(h.supporting_evidence).lower() for h in res.hypotheses)

def test_contradictory_evidence_abstention():
    # Powerless current: 0V input/output but 120A current
    res = diagnose_transformer(
        rated_current_a=100.0,
        current_a=120.0,
        temperature_c=50.0,
        input_voltage_v=0.0,
        output_voltage_v=0.0,
        cooling_ok=True,
        asset_id="TX1",
    )
    assert res.status == "ABSTAINED"
    assert res.abstention is not None
    assert res.abstention.reason == AbstentionReason.CONTRADICTORY_EVIDENCE
    assert "calibration" in res.abstention.next_check_needed.lower()

def test_scoped_missing_telemetry():
    # Current is missing, but cooling is failed and hot
    res = diagnose_transformer(
        rated_current_a=100.0,
        current_a=None,
        temperature_c=92.0,
        input_voltage_v=230.0,
        output_voltage_v=220.0,
        cooling_ok=False,
        asset_id="TX2",
    )
    assert res.status == "FAULT_DETECTED"
    assert any(h.code == "COOLING_FAILURE" for h in res.hypotheses)

def test_total_missing_telemetry_abstention():
    res = diagnose_transformer(
        rated_current_a=100.0,
        current_a=None,
        temperature_c=None,
        input_voltage_v=None,
        output_voltage_v=None,
        cooling_ok=None,
        asset_id="TX3",
    )
    assert res.status == "ABSTAINED"
    assert res.abstention is not None
    assert res.abstention.reason == AbstentionReason.INSUFFICIENT_TELEMETRY

def test_indistinguishable_causes_abstention():
    # Normal input voltage 230V, but 0V output and 0A current without breaker telemetry
    res = diagnose_transformer(
        rated_current_a=100.0,
        current_a=0.0,
        temperature_c=40.0,
        input_voltage_v=230.0,
        output_voltage_v=0.0,
        cooling_ok=True,
        asset_id="TX1",
    )
    assert res.status == "ABSTAINED"
    assert res.abstention is not None
    assert res.abstention.reason == AbstentionReason.INDISTINGUISHABLE_CAUSES
    assert len(res.abstention.indistinguishable_candidates) >= 2

def test_deterministic_ranking_by_severity_and_score():
    # Upstream loss (CRITICAL) vs Thermal stress (MEDIUM)
    res = diagnose_transformer(
        rated_current_a=100.0,
        current_a=0.0,
        temperature_c=85.0,
        input_voltage_v=90.0,
        output_voltage_v=20.0,
        cooling_ok=True,
        asset_id="TX1",
    )
    assert res.status == "FAULT_DETECTED"
    assert res.hypotheses[0].code == "UPSTREAM_LOSS"
    assert res.hypotheses[0].severity == Severity.CRITICAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -k "test_simultaneous_faults" -v`  
Expected: FAIL with `ImportError: cannot import name 'diagnose_transformer'`

- [ ] **Step 3: Implement engine logic**

```python
# backend/app/diagnostics/engine.py
from typing import Optional, List
from app.diagnostics.models import (
    Severity,
    Sufficiency,
    DiagnosticHypothesis,
    AbstentionReason,
    DiagnosticAbstention,
    DiagnosisResult,
)
from app.diagnostics.rules import (
    evaluate_overload,
    evaluate_cooling,
    evaluate_thermal,
    evaluate_upstream_loss,
    evaluate_branch_interrupted,
)

SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.NORMAL: 0,
    Severity.UNKNOWN: -1,
}

def check_contradictions(asset_id: str, current_a: Optional[float], temperature_c: Optional[float],
                         input_voltage_v: Optional[float], output_voltage_v: Optional[float]) -> Optional[DiagnosticAbstention]:
    # Contradiction 1: Powerless Current (current flows while both input and output are unenergized)
    if input_voltage_v is not None and output_voltage_v is not None and current_a is not None:
        if input_voltage_v < 30.0 and output_voltage_v < 30.0 and current_a > 10.0:
            return DiagnosticAbstention(
                asset_id=asset_id,
                reason=AbstentionReason.CONTRADICTORY_EVIDENCE,
                details=f"Current ({current_a:.1f} A) detected while input ({input_voltage_v:.1f} V) and output ({output_voltage_v:.1f} V) are de-energized.",
                contradictory_readings=[f"Input: {input_voltage_v:.1f} V", f"Output: {output_voltage_v:.1f} V", f"Current: {current_a:.1f} A"],
                next_check_needed="Verify current transducer zero-calibration and incoming voltage sensing.",
            )
    # Contradiction 2: Temperature outside plausible physical operating bounds
    if temperature_c is not None:
        if temperature_c < -30.0 or temperature_c > 250.0:
            return DiagnosticAbstention(
                asset_id=asset_id,
                reason=AbstentionReason.CONTRADICTORY_EVIDENCE,
                details=f"Thermocouple reading ({temperature_c:.1f} °C) is outside physical operating limits (-30 °C to 250 °C).",
                contradictory_readings=[f"Temperature: {temperature_c:.1f} °C"],
                next_check_needed="Inspect transformer thermal sensor lead and transducer continuity.",
            )
    return None

def check_indistinguishable_causes(asset_id: str, current_a: Optional[float], input_voltage_v: Optional[float],
                                   output_voltage_v: Optional[float]) -> Optional[DiagnosticAbstention]:
    # Normal incoming supply (>= 180V), but dead output (0V) and zero current
    if input_voltage_v is not None and output_voltage_v is not None and current_a is not None:
        if input_voltage_v >= 180.0 and output_voltage_v < 5.0 and current_a <= 0.1:
            return DiagnosticAbstention(
                asset_id=asset_id,
                reason=AbstentionReason.INDISTINGUISHABLE_CAUSES,
                details="Normal input voltage but completely de-energized output with zero current.",
                indistinguishable_candidates=[
                    "SECONDARY_BREAKER_OPEN",
                    "PRIMARY_FUSE_BLOWN",
                    "SEVERED_DOWNSTREAM_CONDUCTOR",
                ],
                next_check_needed="Check physical transformer secondary breaker trip flag and primary fuse continuity.",
            )
    return None

def diagnose_transformer(
    rated_current_a: float,
    current_a: Optional[float],
    temperature_c: Optional[float],
    input_voltage_v: Optional[float],
    output_voltage_v: Optional[float],
    cooling_ok: Optional[bool],
    asset_id: str = "TX",
) -> DiagnosisResult:
    # 1. Contradiction check
    contradiction = check_contradictions(asset_id, current_a, temperature_c, input_voltage_v, output_voltage_v)
    if contradiction:
        return DiagnosisResult(
            asset_id=asset_id,
            status="ABSTAINED",
            hypotheses=[],
            abstention=contradiction,
            code="UNKNOWN",
            cause=contradiction.details,
            severity="unknown",
            evidence=contradiction.contradictory_readings,
            recommendation=contradiction.next_check_needed,
        )

    # 2. Indistinguishable causes check
    indistinguishable = check_indistinguishable_causes(asset_id, current_a, input_voltage_v, output_voltage_v)
    if indistinguishable:
        return DiagnosisResult(
            asset_id=asset_id,
            status="ABSTAINED",
            hypotheses=[],
            abstention=indistinguishable,
            code="UNKNOWN",
            cause=indistinguishable.details,
            severity="unknown",
            evidence=[f"Candidates: {', '.join(indistinguishable.indistinguishable_candidates)}"],
            recommendation=indistinguishable.next_check_needed,
        )

    # 3. Independent rule evaluations
    hypotheses: List[DiagnosticHypothesis] = []
    
    ov = evaluate_overload(asset_id, rated_current_a, current_a)
    if ov:
        hypotheses.append(ov)
        
    cf = evaluate_cooling(asset_id, temperature_c, cooling_ok)
    if cf:
        hypotheses.append(cf)
        
    th = evaluate_thermal(asset_id, temperature_c, cooling_ok)
    if th and not cf:  # If cooling is broken, cooling_failure captures the fault
        hypotheses.append(th)
        
    up = evaluate_upstream_loss(asset_id, input_voltage_v, output_voltage_v)
    if up:
        hypotheses.append(up)
        
    br = evaluate_branch_interrupted(asset_id, input_voltage_v, output_voltage_v, current_a)
    if br and not up:
        hypotheses.append(br)

    # 4. Shared-cause explanation attribution
    has_overload = any(h.code == "OVERLOAD" for h in hypotheses)
    has_thermal = any(h.code in ("COOLING_FAILURE", "HIGH_TEMPERATURE") for h in hypotheses)
    if has_overload and has_thermal:
        for h in hypotheses:
            if h.code in ("COOLING_FAILURE", "HIGH_TEMPERATURE"):
                h.supporting_evidence.append("Elevated current dissipation compounds transformer thermal stress.")

    # 5. Missing telemetry boundary
    missing = [name for name, val in (
        ("current", current_a),
        ("temperature", temperature_c),
        ("input voltage", input_voltage_v),
        ("output voltage", output_voltage_v),
        ("cooling", cooling_ok),
    ) if val is None]

    if not hypotheses:
        if missing:
            abstention = DiagnosticAbstention(
                asset_id=asset_id,
                reason=AbstentionReason.INSUFFICIENT_TELEMETRY,
                details="Insufficient sensor evidence to evaluate transformer state.",
                missing_sensors=missing,
                next_check_needed=f"Restore sensor telemetry for: {', '.join(missing)}.",
            )
            return DiagnosisResult(
                asset_id=asset_id,
                status="ABSTAINED",
                hypotheses=[],
                abstention=abstention,
                code="UNKNOWN",
                cause=abstention.details,
                severity="unknown",
                evidence=[f"Missing sensors: {', '.join(missing)}"],
                recommendation=abstention.next_check_needed,
            )
        # Normal operation
        evidence = []
        if current_a is not None:
            evidence.append(f"Current {current_a:.1f} A within rating ({rated_current_a * 1.1:.1f} A limit).")
        if temperature_c is not None:
            evidence.append(f"Temperature {temperature_c:.1f} °C below 80.0 °C threshold.")
        if cooling_ok is not None:
            evidence.append("Cooling operational.")
        if input_voltage_v is not None and output_voltage_v is not None:
            evidence.append(f"Input {input_voltage_v:.1f} V, Output {output_voltage_v:.1f} V.")
        return DiagnosisResult(
            asset_id=asset_id,
            status="NORMAL",
            hypotheses=[],
            abstention=None,
            code="NORMAL",
            cause="No configured demo threshold exceeded",
            severity="normal",
            evidence=evidence,
            recommendation="Continue monitoring.",
        )

    # 6. Rank hypotheses: Severity descending, then evidence_score descending
    hypotheses.sort(key=lambda h: (SEVERITY_WEIGHTS.get(h.severity, 0), h.evidence_score), reverse=True)
    top = hypotheses[0]

    all_evidence = []
    for h in hypotheses:
        all_evidence.extend(h.supporting_evidence)

    return DiagnosisResult(
        asset_id=asset_id,
        status="FAULT_DETECTED",
        hypotheses=hypotheses,
        abstention=None,
        code=top.code,
        cause=top.cause if len(hypotheses) == 1 else f"Multiple co-occurring faults ({', '.join(h.code for h in hypotheses)})",
        severity=top.severity.value,
        evidence=all_evidence,
        recommendation=top.recommendation,
    )
```

```python
# update backend/app/diagnostics/__init__.py
from app.diagnostics.models import (
    Severity,
    Sufficiency,
    DiagnosticHypothesis,
    AbstentionReason,
    DiagnosticAbstention,
    DiagnosisResult,
)
from app.diagnostics.engine import diagnose_transformer

__all__ = [
    "Severity",
    "Sufficiency",
    "DiagnosticHypothesis",
    "AbstentionReason",
    "DiagnosticAbstention",
    "DiagnosisResult",
    "diagnose_transformer",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/diagnostics/ backend/tests/test_diagnostics.py
git commit -m "diagnostics: implement engine with ranking, contradictions and abstentions"
```

---

### Task 4: Visualizer Integration (`backend/app/visualizers.py`)

**Files:**
- Modify: `backend/app/visualizers.py:174-230`
- Modify: `backend/tests/test_visualizers.py:40-55`

**Interfaces:**
- Consumes: `app.diagnostics.diagnose_transformer`
- Produces: `app.visualizers.diagnose(...) -> dict`, `app.visualizers.hospital_snapshot(...) -> dict`

- [ ] **Step 1: Write the failing test for hospital snapshot diagnosis compatibility and enrichment**

```python
# in backend/tests/test_visualizers.py
def test_hospital_diagnosis_multi_hypothesis_and_backward_compatibility():
    # Multi-fault simultaneous scenario
    simul = diagnose(100.0, current_a=130.0, temperature_c=91.0, input_voltage_v=230.0, output_voltage_v=218.0, cooling_ok=False)
    assert "hypotheses" in simul
    assert len(simul["hypotheses"]) >= 2
    assert simul["severity"] == "high"
    # Backward compatible fields exist
    assert "code" in simul
    assert "cause" in simul
    assert "evidence" in simul
    assert "recommendation" in simul
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_visualizers.py -k "test_hospital_diagnosis_multi_hypothesis" -v`  
Expected: FAIL with `AssertionError: assert 'hypotheses' in simul`

- [ ] **Step 3: Update `app/visualizers.py` to use `diagnose_transformer`**

In `backend/app/visualizers.py`:
Replace lines 174-198 with:
```python
from app.diagnostics import diagnose_transformer

def diagnose(rated_current_a, current_a, temperature_c, input_voltage_v, output_voltage_v, cooling_ok, asset_id="TX"):
    """Classify provided synthetic sensor observations using telemetry-derived hypothesis engine."""
    result = diagnose_transformer(
        rated_current_a=rated_current_a,
        current_a=current_a,
        temperature_c=temperature_c,
        input_voltage_v=input_voltage_v,
        output_voltage_v=output_voltage_v,
        cooling_ok=cooling_ok,
        asset_id=asset_id,
    )
    return result.model_dump()
```
And in `hospital_snapshot`:
Pass `asset_id=f"TX{i}"` to `diagnose(100.0, **sensors, asset_id=f"TX{i}")`.

- [ ] **Step 4: Run visualizer and diagnostics tests**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_visualizers.py backend/tests/test_diagnostics.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/visualizers.py backend/tests/test_visualizers.py
git commit -m "visualizers: delegate hospital diagnosis to multi-hypothesis engine"
```

---

### Task 5: Campus Telemetry Diagnostic Integration (`backend/app/core/state.py`)

**Files:**
- Modify: `backend/app/core/state.py:107-130`
- Modify: `backend/app/schemas/snapshot.py:76-81`
- Modify: `backend/tests/test_state.py` or new test in `backend/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: `app.diagnostics.models` (`DiagnosticHypothesis`, `Severity`)
- Produces: `GridState.fault_diagnosis` populated with structured candidate hypotheses

- [ ] **Step 1: Write test verifying campus diagnosis does not leak simulator oracle and provides hypotheses**

```python
# append to backend/tests/test_diagnostics.py
from app.core.state import GridState

def test_campus_state_fault_diagnosis_structured():
    state = GridState()
    state.set_capacity(7000)
    state.set_feeder("F1", False)
    diag = state.fault_diagnosis
    assert diag is not None
    assert diag.has_fault is True
    assert diag.severity == "HIGH"
    assert hasattr(diag, "hypotheses")
    codes = [h["code"] if isinstance(h, dict) else h.code for h in diag.hypotheses]
    assert "GRID_CAPACITY_SHORTFALL" in codes
    assert "FEEDER_DISCONNECTED" in codes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -k "test_campus_state_fault_diagnosis" -v`  
Expected: FAIL with `AssertionError: assert hasattr(diag, 'hypotheses')`

- [ ] **Step 3: Update `FaultDiagnosis` schema and `GridState.compute_fault_diagnosis`**

In `backend/app/schemas/snapshot.py`:
```python
class FaultDiagnosis(BaseModel):
    has_fault: bool
    diagnosis: str
    severity: str
    status: str
    hypotheses: List[Dict[str, object]] = Field(default_factory=list)
```

In `backend/app/core/state.py`:
Update `compute_fault_diagnosis()`:
```python
            if has_fault:
                severity = "HIGH" if not all(self.feeder_available.values()) else "MEDIUM"
                hypotheses_list = []
                if self.source_capacity_w < 14000:
                    hypotheses_list.append({
                        "id": "CAMPUS:SUPPLY_SHORTFALL",
                        "code": "GRID_CAPACITY_SHORTFALL",
                        "asset_id": "MAIN_SUPPLY",
                        "cause": f"Observed grid capacity ({self.source_capacity_w} W) below 14 kW rating",
                        "severity": "medium",
                        "evidence_score": 0.85,
                        "supporting_evidence": [f"Current capacity: {self.source_capacity_w} W"],
                        "recommendation": "Initiate automated load shedding to protect critical services.",
                    })
                for f, avail in self.feeder_available.items():
                    if not avail:
                        hypotheses_list.append({
                            "id": f"FEEDER:{f}:DISCONNECTED",
                            "code": "FEEDER_DISCONNECTED",
                            "asset_id": f"FEEDER_{f}",
                            "cause": f"Feeder {f} interruption detected",
                            "severity": "high",
                            "evidence_score": 0.95,
                            "supporting_evidence": [f"Feeder line telemetry reports line open."],
                            "recommendation": f"Inspect breaker and feeder line {f}.",
                        })
                self.fault_diagnosis = FaultDiagnosis(
                    has_fault=True,
                    diagnosis=" ".join(diagnosis_msgs),
                    severity=severity,
                    status="ACTIVE",
                    hypotheses=hypotheses_list,
                )
```

- [ ] **Step 4: Run tests to verify it passes**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with pytest python -m pytest backend/tests/test_diagnostics.py -k "test_campus_state_fault_diagnosis" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/snapshot.py backend/app/core/state.py backend/tests/test_diagnostics.py
git commit -m "state: structure campus fault diagnosis with candidate hypotheses"
```

---

### Task 6: Frontend Types and UI Presentation (`frontend/src/`)

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/pages/HospitalDemo.tsx`

**Interfaces:**
- Consumes: Updated backend `DiagnosisResult` with `hypotheses` and `abstention`
- Produces: Enhanced UI displaying multi-hypothesis tags, uncalibrated evidence scores, and abstention warnings

- [ ] **Step 1: Update TypeScript interfaces in `frontend/src/types.ts`**

Add:
```typescript
export interface DiagnosticHypothesis {
  id: string;
  code: string;
  asset_id: string;
  cause: string;
  severity: "critical" | "high" | "medium" | "low" | "normal" | "unknown";
  evidence_score: number;
  sufficiency: "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT";
  supporting_evidence: string[];
  contradicting_evidence: string[];
  recommendation: string;
}

export interface DiagnosticAbstention {
  asset_id: string;
  reason: "INSUFFICIENT_TELEMETRY" | "CONTRADICTORY_EVIDENCE" | "INDISTINGUISHABLE_CAUSES";
  details: string;
  missing_sensors: string[];
  contradictory_readings: string[];
  indistinguishable_candidates: string[];
  next_check_needed: string;
}

export interface HospitalDemoDiagnosis {
  code: string;
  cause: string;
  severity: string;
  evidence: string[];
  recommendation: string;
  status?: "NORMAL" | "FAULT_DETECTED" | "ABSTAINED";
  hypotheses?: DiagnosticHypothesis[];
  abstention?: DiagnosticAbstention | null;
}
```

- [ ] **Step 2: Update `frontend/src/pages/HospitalDemo.tsx` to render hypotheses & abstention**

In `frontend/src/pages/HospitalDemo.tsx`:
- Render multiple hypothesis tags if `transformer.diagnosis.hypotheses` has length > 1, each badge displaying the code, severity styling, and `evidence_score` with `Heuristic score (uncalibrated)`.
- If `transformer.diagnosis.abstention` exists, render an abstention callout card:
  - Header: `Abstained: {abstention.reason.replace(/_/g, ' ')}`
  - Detail text: `abstention.details`
  - Callout: `Next check needed: {abstention.next_check_needed}`

- [ ] **Step 3: Run TypeScript compiler and production build**

Run: `cd frontend && npm run build`  
Expected: PASS (built cleanly with no TypeScript errors)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/pages/HospitalDemo.tsx
git commit -m "frontend: display multi-hypothesis badges and diagnostic abstention cards"
```

---

### Task 7: End-to-End Verification & Documentation Update

**Files:**
- Modify: `CONTEXT.md`
- Modify: `PROGRESS_REPORT.md`
- Run: Full backend tests and frontend build

- [ ] **Step 1: Run full backend test suite**

Run: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with-requirements backend/requirements-ml.txt --with pytest --with httpx python -m pytest backend/tests -q`  
Expected: PASS (all tests pass)

- [ ] **Step 2: Run frontend production build**

Run: `cd frontend && npm run build`  
Expected: PASS

- [ ] **Step 3: Update `CONTEXT.md` and `PROGRESS_REPORT.md`**

Record the completion of BM-17 / Issue #19, commands run, test counts, and verified evidence.

- [ ] **Step 4: Commit**

```bash
git add CONTEXT.md PROGRESS_REPORT.md
git commit -m "docs: record BM-17 multi-hypothesis diagnosis delivery and verification"
```
