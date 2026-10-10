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
