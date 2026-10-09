from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class HardwareLinkStatus(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"

class SourceKind(str, Enum):
    SIMULATED = "SIMULATED"
    PHYSICAL = "PHYSICAL"

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

class HospitalRoom(BaseModel):
    id: str
    name: str
    lighting_service: str  # always "L0"
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

class SystemSnapshot(BaseModel):
    control_revision: int
    generated_at: datetime
    source: SourceInfo
    feeder_limits_w: dict[str, int]
    requested_mask: int
    modeled_mask: int
    indicator_mask: Optional[int] = None
    indicator_command_mask: Optional[int] = None
    indicator_confirmed_mask: Optional[int] = None
    zones: Optional[FacilityZones] = None
    hardware_link: HardwareLinkStatus
    services: List[ServiceSnapshot]

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
    capacity_w: int = Field(gt=0, le=20000)

class CapacityChangeResponse(BaseModel):
    accepted: bool
    new_capacity_w: int
    control_revision: int

class ClassroomLoadRequest(BaseModel):
    classroom_id: str
    active: bool

class ClassroomLoadResponse(BaseModel):
    accepted: bool
    classroom_id: str
    load_event_active: bool

class FeederChangeRequest(BaseModel):
    feeder: str
    available: bool

class FeederChangeResponse(BaseModel):
    accepted: bool
    feeder: str
    available: bool
    control_revision: int
