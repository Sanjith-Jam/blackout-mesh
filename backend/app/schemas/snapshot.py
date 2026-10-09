from pydantic import BaseModel, Field, ConfigDict, StrictStr, StrictFloat, StrictInt, StrictBool
from enum import Enum
from typing import List, Optional, Dict
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
    SESSION_ENDED = "SESSION_ENDED"

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
    timestamp: str
    type: str
    description: str


class Hypothesis(BaseModel):
    code: str
    cause: str
    asset_id: Optional[str] = None
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    time_window: str
    sufficiency: str
    score: float
    severity: str
    recommendation: str

class RankedDiagnosis(BaseModel):
    is_fault: bool
    hypotheses: List[Hypothesis]
    abstention_reason: Optional[str] = None


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
    control_revision: int
    config_hash: str = ""
    generated_at: datetime
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
    fault_diagnosis: Optional[RankedDiagnosis] = None
    activity: Dict[str, "ActivitySnapshot"] = Field(default_factory=dict)
    model: Dict[str, object] = Field(default_factory=dict)
    replay: "ReplaySnapshot"
    allocation: "AllocationSnapshot"


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


class ReplaySnapshot(BaseModel):
    running: bool
    index: int
    length: int


class AllocationSnapshot(BaseModel):
    objective: str
    critical_shortfall_w: int
    served_w: int
    baseline_mask: int


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
    config_hash: str = ""

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
    config_hash: str = ""


class HealthResponse(BaseModel):
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
    id: str
    name: str
    watts: int
    essential: bool
    served: bool
    reason: str

class ClassroomDemoRoom(BaseModel):
    id: str
    name: str
    rfid_active: bool
    loads: List[ClassroomDemoLoad]

class ClassroomDemoSnapshot(BaseModel):
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
    code: str
    cause: str
    severity: str
    evidence: List[str]
    recommendation: str
    hypotheses: List[Hypothesis]

class HospitalDemoTransformer(BaseModel):
    id: str
    name: str
    zone: str
    rated_current_a: float
    sensors: HospitalDemoSensors
    diagnosis: HospitalDemoDiagnosis
    energized: bool

class HospitalDemoSnapshot(BaseModel):
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
    type: str
    payload: SystemSnapshot
