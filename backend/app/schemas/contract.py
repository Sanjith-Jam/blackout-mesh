from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime

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
    observation_time: datetime

class CrossRouteContract(BaseModel):
    identity: RunIdentity
    campus_totals: ScopeTotals
    zone_totals: Dict[str, ScopeTotals]
