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

from app.core.state import GridState

def test_campus_state_fault_diagnosis_structured():
    state = GridState()
    state.set_capacity(7000)
    state.set_feeder("A", False)
    state.tick()
    state.tick()  # telemetry-only diagnosis (#4) confirms on the second agreeing reading
    diag = state.fault_diagnosis
    assert diag is not None
    assert diag.has_fault is True
    assert diag.severity == "HIGH"
    assert hasattr(diag, "hypotheses")
    codes = [h["code"] if isinstance(h, dict) else h.code for h in diag.hypotheses]
    assert "FEEDER_DISCONNECTED" in codes
    # A configured capacity limit is an operating constraint, never fault evidence (#4).
    assert "GRID_CAPACITY_SHORTFALL" not in codes
    assert "7000" in diag.supply_constraint




