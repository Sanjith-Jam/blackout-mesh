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
