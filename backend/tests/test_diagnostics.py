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

