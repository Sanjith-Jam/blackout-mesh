"""Appliance-level power-system projection (GET /api/v1/power-system).

Every value carries its provenance: CONFIGURED (site profile, a simulated demonstration assumption),
MODELED (the optimizer's applied decision), DERIVED (arithmetic on configured and modeled values),
SIMULATED_TELEMETRY (synthetic sensor envelopes the diagnosis reads), INJECTED_SIMULATION (a fault the
operator switched on) or PHYSICAL (only when a device reports it).
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, StrictBool, StrictStr

from app.schemas.snapshot import SiteIdentityResponse

ApplianceState = Literal["SERVED", "PENDING_RESTORATION", "SHED", "UNREACHABLE", "NOT_REQUESTED"]
EdgeState = Literal["ENERGIZED", "PENDING_RESTORATION", "SHED", "OPEN", "UNKNOWN"]


class ApplianceEvent(BaseModel):
    timestamp: str
    appliance_id: str
    to: str
    from_state: Optional[str] = None
    reason: str
    command: Optional[str] = None
    provenance: str


class Appliance(BaseModel):
    id: str
    asset_id: str
    key: str
    name: str
    room_id: str
    zone: str
    feeder: str
    service_id: str
    distribution_id: str
    demand_w: int
    service_tier: str
    essential: bool
    protected: bool
    priority_class: str
    priority_label: str
    priority_rank: int
    requested: bool
    reachable: bool
    commanded: bool
    served: bool
    served_w: int
    state: ApplianceState
    reason_code: str
    reason: str
    path: List[str]
    requires: List[str]
    indivisible_group: Optional[str] = None
    provenance: str
    events: List[ApplianceEvent]


class Room(BaseModel):
    id: str
    name: str
    zone: str
    feeder: str
    distribution_id: str
    distribution_name: str
    service_id: Optional[str] = None
    requested_w: int
    commanded_w: int
    served_w: int
    session: Optional[bool] = None
    activity_state: Optional[str] = None
    evidence_status: str
    evidence_detail: Optional[str] = None


class Feeder(BaseModel):
    id: str
    name: str
    available: bool
    limit_w: int
    requested_w: int
    commanded_w: int
    served_w: int


class Source(BaseModel):
    id: str
    name: str
    capacity_w: int
    normal_capacity_w: int
    requested_w: int
    commanded_w: int
    served_w: int
    provenance: str


class ZoneBudget(BaseModel):
    zone: str
    limit_w: int
    normal_limit_w: int
    requested_w: int
    served_w: int


class Edge(BaseModel):
    id: str
    from_node: str
    to_node: str
    kind: str
    state: EdgeState
    requested_w: int
    served_w: int


class ConstraintCheck(BaseModel):
    id: str
    scope: str
    label: str
    requested_w: int
    limit_w: int
    served_w: int
    exceeded: bool
    deficit_w: int
    headroom_w: int
    provenance: str


class ActiveFault(BaseModel):
    id: str
    kind: str
    target: str
    description: str
    provenance: str


class Indicator(BaseModel):
    led_bit: int
    room_id: str
    name: str
    rule: str
    commanded: bool
    confirmed: Optional[bool] = None


class PowerSystemResponse(BaseModel):
    site: SiteIdentityResponse
    generated_at: str
    boundary: str
    source: Source
    feeders: List[Feeder]
    zone_budgets: List[ZoneBudget]
    rooms: List[Room]
    appliances: List[Appliance]
    edges: List[Edge]
    optimizer: Dict[str, Any]
    diagnosis: Dict[str, Any]
    constraint_checks: List[ConstraintCheck]
    faults: List[ActiveFault]
    indicators: List[Indicator]
    hardware_link: str
    events: List[Dict[str, Any]]
    appliance_events: List[ApplianceEvent]


class ApplianceRequest(BaseModel):
    appliance_id: StrictStr
    requested: StrictBool


class ApplianceRequestResponse(BaseModel):
    accepted: bool
    appliance_id: str
    requested: bool
    site: SiteIdentityResponse
