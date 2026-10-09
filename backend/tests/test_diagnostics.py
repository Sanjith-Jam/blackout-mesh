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
