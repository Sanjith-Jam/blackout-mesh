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
