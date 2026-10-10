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


class SiteIdentityResponse(BaseModel):
    run_id: str
    revision: int
    profile: str
    catalog_version: str
    config_hash: str
    site_name: str

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
    site: Optional[SiteIdentityResponse] = None
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
    uid: StrictStr = Field(min_length=1, max_length=256)
    event_id: StrictStr = Field(min_length=1, max_length=128)
    observed_at: datetime
    run_id: StrictStr = Field(min_length=1, max_length=100)

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
    event_id: StrictStr = Field(min_length=1, max_length=128)
    observed_at: datetime
    run_id: StrictStr = Field(min_length=1, max_length=100)

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
    control_loop: "ControlLoopHealth"
    storage: "StorageHealth"
    status: str
    application: str


class ControlLoopHealth(BaseModel):
    running: bool
    period_s: float
    tick_count: int
    missed_ticks: int
    errors: int
    last_error: Optional[str] = None
    last_tick_age_s: Optional[float] = None
    last_tick_at: Optional[datetime] = None


class StorageHealth(BaseModel):
    status: Literal["HEALTHY", "DEGRADED"]
    degraded_reason: Optional[str] = None


class APIErrorResponse(BaseModel):
    detail: str | List[Dict[str, object]]

class ModelStatusResponse(BaseModel):
    ready: bool
    model_version: str
    model_type: str
    features: List[str]
    data_source: str
    evaluation: Dict[str, object] = Field(default_factory=dict)
    fallback_reason: Optional[str] = None


class CommandReceipt(BaseModel):
    command_id: str
    name: str
    run_id: str
    applied_revision: int


class PowerEdge(BaseModel):
    id: str
    from_: str = Field(alias="from")
    to: str
    state: Literal["ENERGIZED", "PENDING_RESTORATION", "SHED", "OPEN", "UNKNOWN"]
    connected: bool
    commanded: bool
    applied: bool
    requested_w: int
    served_w: int
    unit: Literal["W"]
    provenance: Literal["MODELED"]
    physical: Literal["NOT_CONNECTED", "CONFIRMED"]
    reason: str
    observed: Optional["PowerEdgeObservation"] = None

    model_config = ConfigDict(populate_by_name=True)


class PowerEdgeObservation(BaseModel):
    output_voltage_v: Optional[float] = None
    energized: Optional[bool] = None
    provenance: str
    diagnosis_status: Optional[str] = None
    note: str


class HardwareStatusResponse(BaseModel):
    link: Literal["NOT_CONFIGURED", "CONNECTING", "SYNCING", "CONNECTED", "STALE"]
    commanded_mask: Optional[int] = None
    confirmed_mask: Optional[int] = None
    led_confirmed: Optional[bool] = None
    board_a: Optional["BoardAStatus"] = None
    board_b: Optional["BoardBStatus"] = None
    session: Optional[int | str] = None
    last_radio_result: Optional[str] = None
    recent_events: List["HardwareEvent"] = Field(default_factory=list)
    recent_status: List[str] = Field(default_factory=list)
    port_error: Optional[str] = None


class BoardAStatus(BaseModel):
    boot: Optional[int] = None
    reader_ok: Optional[bool] = None
    radio_configured: Optional[bool] = None


class BoardBStatus(BaseModel):
    online: bool
    boot: Optional[int] = None
    radio_ready: bool


class HardwareEvent(BaseModel):
    event: int
    action: str
    room: Optional[str] = None
    accepted: bool


class VisualizerLoad(BaseModel):
    id: str
    name: Optional[str] = None
    watts: Optional[int] = None
    essential: Optional[bool] = None
    served: bool
    reason: Optional[str] = None


class ClassroomDemoLoadResponse(BaseModel):
    id: str
    name: str
    watts: int
    essential: bool
    served: bool
    reason: str


class VisualizerActivity(BaseModel):
    state: Literal["ACTIVE", "INACTIVE", "UNKNOWN"]
    raw_state: Optional[Literal["ACTIVE", "INACTIVE", "UNKNOWN"]] = None
    guard: Optional[str] = None
    score: Optional[float]
    reason: str
    model_version: str
    evidence: Dict[str, Optional[float]]


class VisualizerModelStatus(BaseModel):
    ready: bool
    model_version: str
    fallback_reason: Optional[str] = None


class VisualizerReplay(BaseModel):
    running: bool
    index: int
    length: int
    step_s: float


class DiagnosticHypothesisResponse(BaseModel):
    id: str
    code: str
    asset_id: str
    cause: str
    severity: str
    evidence_score: float
    sufficiency: str
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    recommendation: str


class DiagnosticAbstentionResponse(BaseModel):
    asset_id: str
    reason: str
    details: str
    missing_sensors: List[str]
    contradictory_readings: List[str]
    indistinguishable_candidates: List[str]
    next_check_needed: str


class HospitalDiagnosisResponse(BaseModel):
    code: str
    cause: str
    severity: str
    evidence: List[str]
    recommendation: str
    hypotheses: List[DiagnosticHypothesisResponse]
    status: Optional[str] = None
    abstention: Optional[DiagnosticAbstentionResponse] = None
    missing: List[str] = Field(default_factory=list)
    stale: List[str] = Field(default_factory=list)


class ClassroomDemoRoomResponse(BaseModel):
    id: str
    name: str
    rfid_active: bool
    priority_rank: Optional[int] = None
    activity: VisualizerActivity
    loads: List[ClassroomDemoLoadResponse]


class ClassroomDemoResponse(BaseModel):
    contract: CrossRouteContract
    site: Optional[SiteIdentityResponse] = None
    published_revision: Optional[int] = None
    capacity_w: int
    capacity_range_w: List[int]
    classroom_limit_w: int
    campus_limit_w: Optional[int] = None
    effective_capacity_w: int
    limited_by: Literal["classroom limit", "campus feeder B"]
    requested_w: int
    served_w: int
    shortfall_w: int
    selected_classroom_id: Optional[str] = None
    scanned_classroom_ids: List[str]
    priority_order: List[str]
    rooms: List[ClassroomDemoRoomResponse]
    mode: Literal["SIMULATED"]
    safety: SafetySnapshot
    edges: List[PowerEdge] = Field(default_factory=list)
    generated_at: Optional[datetime] = None
    command: Optional[CommandReceipt] = None
    hardware: Optional[HardwareStatusResponse] = None
    model: VisualizerModelStatus
    replay: VisualizerReplay
    policy: str


class HospitalDemoTransformerResponse(BaseModel):
    id: str
    name: str
    zone: str
    rated_current_a: Optional[float] = None
    sensors: HospitalDemoSensors
    diagnosis: HospitalDiagnosisResponse
    energized: bool
    rfid_active: Optional[bool] = None
    priority_rank: Optional[int] = None
    activity: Optional[VisualizerActivity] = None
    loads: List[VisualizerLoad]


class HospitalFaultResponse(BaseModel):
    kind: Literal["overload", "cooling_failure", "overload_cooling", "upstream_loss", "sensor_dropout", "stuck_sensor"]
    zone_id: str
    asset_id: str
    provenance: Literal["INJECTED_SIMULATION"]


class HospitalDemoResponse(BaseModel):
    contract: CrossRouteContract
    site: Optional[SiteIdentityResponse] = None
    mode: Literal["SIMULATED"]
    transformers: List[HospitalDemoTransformerResponse]
    summary: Optional[str] = None
    capacity_w: Optional[int] = None
    capacity_range_w: Optional[List[int]] = None
    hospital_limit_w: Optional[int] = None
    campus_limit_w: Optional[int] = None
    effective_capacity_w: Optional[int] = None
    limited_by: Optional[Literal["hospital limit", "campus feeder A"]] = None
    fault: Optional[HospitalFaultResponse] = None
    requested_w: Optional[int] = None
    served_w: Optional[int] = None
    shortfall_w: Optional[int] = None
    selected_zone_id: Optional[str] = None
    scanned_zone_ids: List[str] = Field(default_factory=list)
    priority_order: List[str] = Field(default_factory=list)
    safety: Optional[Dict[str, object]] = None
    edges: List[PowerEdge] = Field(default_factory=list)
    generated_at: Optional[datetime] = None
    command: Optional[CommandReceipt] = None
    model: Optional[VisualizerModelStatus] = None
    replay: Optional[VisualizerReplay] = None
    policy: Optional[str] = None


class AllocationPolicyResponse(BaseModel):
    name: Literal["activity_first", "water_first"]
    version: Literal["allocation-v1"]
    fairness_weight: int
    switching_penalty: int


class AllocationPolicyUpdateResponse(BaseModel):
    policy: AllocationPolicyResponse
    receipt: CommandReceipt


class HistoryRunResponse(BaseModel):
    site_id: str
    run_id: str
    started_at: str
    pruned_through: int


class HistoryRunsResponse(BaseModel):
    current_run_id: str
    runs: List[HistoryRunResponse]


class HistoryRecordBase(BaseModel):
    seq: int
    record_id: str
    site_id: str
    run_id: str
    timestamp: str
    revision: int
    provenance: str


class HistoryEventPayload(BaseModel):
    event: SystemEvent
    inputs: Dict[str, object] = Field(default_factory=dict)


class HistoryDecisionPayload(BaseModel):
    snapshot: SystemSnapshot
    inputs: Dict[str, object]
    policy: Dict[str, object]
    model: Dict[str, object]
    event_ids: List[str]
    trail: Dict[str, object]


class HistoryTelemetryPayload(BaseModel):
    state_generated_at: str
    capacity: int
    demand: int
    servedCount: int
    shedCount: int


class HistoryEventRecord(HistoryRecordBase):
    kind: Literal["event"]
    payload: HistoryEventPayload


class HistoryDecisionRecord(HistoryRecordBase):
    kind: Literal["decision"]
    payload: HistoryDecisionPayload


class HistoryTelemetryRecord(HistoryRecordBase):
    kind: Literal["telemetry"]
    payload: HistoryTelemetryPayload


class HistoryPageResponse(BaseModel):
    items: List[HistoryEventRecord | HistoryDecisionRecord | HistoryTelemetryRecord]
    next_cursor: Optional[int] = None
    retention_gap: bool
    pruned_through: int


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
    type: Literal["snapshot"]
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
