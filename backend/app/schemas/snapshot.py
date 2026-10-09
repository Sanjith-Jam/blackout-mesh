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

class SystemSnapshot(BaseModel):
    control_revision: int
    generated_at: datetime
    source: SourceInfo
    feeder_limits_w: dict[str, int]
    requested_mask: int
    modeled_mask: int
    indicator_mask: Optional[int] = None
    hardware_link: HardwareLinkStatus
    services: List[ServiceSnapshot]
