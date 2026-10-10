from pydantic import BaseModel, Field, ConfigDict, StrictStr, StrictFloat, StrictInt, StrictBool
from enum import Enum
from typing import List, Optional, Dict, Literal
from datetime import datetime

class HardwareLinkStatus(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"

class SourceKind(str, Enum):
    SIMULATED = "SIMULATED"

class Tier(str, Enum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"

class SourceInfo(BaseModel):
    model: Literal["watt_budget"] = "watt_budget"
    limitations: str = "Integer demand/capacity accounting; no AC power flow, thermal dynamics or protection physics"
    kind: SourceKind
    capacity_w: int

class ServiceSnapshot(BaseModel):
    id: str
    name: str
    tier: Tier
    feeder: str
    watts: int
    requested: bool
    modeled_served: bool
    indicator_confirmed: Optional[bool] = None
    model_reason: str

class RfidReaderStatus(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"

class RfidEventType(str, Enum):
    CARD_RECOGNIZED = "CARD_RECOGNIZED"
    UNKNOWN_CARD = "UNKNOWN_CARD"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"

class HospitalRoom(BaseModel):
    id: str
    name: str
    lighting_service: str
    led_bit: int

class ClassroomInfo(BaseModel):
    id: str
    name: str
    service_id: str
    rfid_card_registered: bool
    led_bit: int
    load_event_active: bool

class HospitalZone(BaseModel):
    rooms: List[HospitalRoom]

class ClassroomZone(BaseModel):
    active_classroom_id: Optional[str] = None
    recent_rfid_scan: Optional[str] = None
    rfid_reader_status: RfidReaderStatus = RfidReaderStatus.NOT_CONNECTED
    classrooms: List[ClassroomInfo]

class FacilityZones(BaseModel):
    hospital: HospitalZone
    classroom: ClassroomZone

class SystemEvent(BaseModel):
    event_id: str | None = None
    run_id: str | None = None
    revision: int = 0
    timestamp: str
    type: str
    description: str

class FaultDiagnosis(BaseModel):
    has_fault: bool
    diagnosis: str
    severity: str
    status: str  # NORMAL | FAULT_DETECTED | ALARM | ABSTAINED (telemetry-derived, #4/#19)
    hypotheses: List[Dict[str, object]] = Field(default_factory=list)
    affected_assets: List[str] = Field(default_factory=list)
    supply_constraint: Optional[str] = None  # configured limit, never fault evidence

class ScopeTotals(BaseModel):
    capacity_w: Optional[int] = None
    requested_w: int
    served_w: int

class RunIdentity(BaseModel):
    site_id: str
    run_id: str
    server_epoch: int
    config_hash: str
    catalog_version: str
    policy_version: str
    model_version: str
    state_revision: int
    observation_time: str

class CrossRouteContract(BaseModel):
    identity: RunIdentity
    campus_totals: Optional[ScopeTotals] = None
    zone_totals: Dict[str, ScopeTotals] = {}

class SystemSnapshot(BaseModel):
    contract: CrossRouteContract
    config_hash: str = ""
    control_revision: int
    generated_at: datetime
    published_revision: int = 0
    source: SourceInfo
    feeder_limits_w: Dict[str, int]
    requested_mask: int
    modeled_mask: int
    proposed_mask: int = 0
    indicator_command_mask: Optional[int] = None
    indicator_confirmed_mask: Optional[int] = None
    indicator_mask: Optional[int] = None
    hardware_link: HardwareLinkStatus
    services: List[ServiceSnapshot]
    zones: Optional[FacilityZones] = None
    events: List[SystemEvent] = []
    fault_diagnosis: Optional[FaultDiagnosis] = None
    activity: Dict[str, "ActivitySnapshot"] = Field(default_factory=dict)
    model: Dict[str, object] = Field(default_factory=dict)
    replay: "ReplaySnapshot"
    allocation: "AllocationSnapshot"
    site: Optional[Dict[str, object]] = None
    edges: List[Dict[str, object]] = Field(default_factory=list)  # canonical power paths (#23)


class ActivityObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    classroom_id: StrictStr
    temperature_c: Optional[StrictFloat | StrictInt] = None
    humidity_pct: Optional[StrictFloat | StrictInt] = None
    co2_ppm: Optional[StrictFloat | StrictInt] = None
    humidity_ratio: Optional[StrictFloat | StrictInt] = None
    observed_at: StrictStr
    source: StrictStr


class ActivitySnapshot(BaseModel):
    state: str
    score: Optional[float] = None
    reason: str
    source: Optional[str] = None
    observed_at: Optional[datetime] = None
    model_version: str
    priority: str
    evidence: Optional[Dict[str, Optional[float]]] = None
    raw_state: Optional[str] = None
    guard: Optional[str] = None


class ReplaySnapshot(BaseModel):
    running: bool
    index: int
    length: int


class SafetySnapshot(BaseModel):
    policy_version: str
    status: str
    protected_requested_w: int
    protected_served_w: int
    protected_shortfall_w: int
    fallback_order: List[str]


class AllocationSnapshot(BaseModel):
    explanation: dict = Field(default_factory=dict)
    objective: str
    critical_shortfall_w: int
    served_w: int
    baseline_mask: int
    safety: Optional[SafetySnapshot] = None


class ReplayActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: StrictStr

class RfidScanRequest(BaseModel):
    uid: str
    event_id: Optional[str] = None

class RfidScanResponse(BaseModel):
    accepted: bool
    active_classroom_id: Optional[str] = None
    classroom_name: Optional[str] = None
    service_id: Optional[str] = None
    event_type: RfidEventType

class CapacityChangeRequest(BaseModel):
    capacity_w: StrictInt = Field(ge=0, le=20000)

class CapacityChangeResponse(BaseModel):
    accepted: bool
    new_capacity_w: int
    control_revision: int

class ClassroomLoadRequest(BaseModel):
    classroom_id: StrictStr
    active: StrictBool

class ClassroomLoadResponse(BaseModel):
    accepted: bool
    classroom_id: str
    load_event_active: bool

class FeederChangeRequest(BaseModel):
    feeder: StrictStr
    available: StrictBool

class FeederChangeResponse(BaseModel):
    accepted: bool
    feeder: str
    available: bool
    control_revision: int


class HealthResponse(BaseModel):
    control_loop: dict = Field(default_factory=dict)
    status: str
    application: str

class ModelStatusResponse(BaseModel):
    ready: bool
    model_version: str
    model_type: str
    features: List[str]
    data_source: str
    evaluation: Dict[str, object] = Field(default_factory=dict)
    fallback_reason: Optional[str] = None

class ClassroomDemoLoad(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    watts: int
    essential: bool
    served: bool
    reason: str

class ClassroomDemoRoom(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    rfid_active: bool
    loads: List[ClassroomDemoLoad]

class ClassroomDemoSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")
    contract: CrossRouteContract
    capacity_w: int
    requested_w: int
    served_w: int
    shortfall_w: int
    selected_classroom_id: Optional[str] = None
    rooms: List[ClassroomDemoRoom]
    mode: str
    policy: str

class HospitalDemoSensors(BaseModel):
    current_a: Optional[float] = None
    temperature_c: Optional[float] = None
    input_voltage_v: Optional[float] = None
    output_voltage_v: Optional[float] = None
    cooling_ok: Optional[bool] = None

class HospitalDemoDiagnosis(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str
    cause: str
    severity: str
    evidence: List[str]
    recommendation: str
    hypotheses: List[Dict[str, object]]

class HospitalDemoTransformer(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    zone: str
    rated_current_a: float
    sensors: HospitalDemoSensors
    diagnosis: HospitalDemoDiagnosis
    energized: bool

class HospitalDemoSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")
    contract: CrossRouteContract
    mode: str
    transformers: List[HospitalDemoTransformer]
    summary: str

class ActivityObservationResponse(BaseModel):
    accepted: bool
    applied: bool
    revision: int
    activity: ActivitySnapshot

class ReplayActionResponse(BaseModel):
    running: bool
    index: int
    length: int

class WebSocketMessageEnvelope(BaseModel):
    sent_at: datetime
    type: str
    payload: SystemSnapshot

class HardwareAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_boot: str
    sequence: int
    session: str
    confirmed_mask: int
    provenance: str

class HardwareAckResponse(BaseModel):
    accepted: bool
