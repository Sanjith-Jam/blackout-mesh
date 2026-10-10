import json
import os
from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional, Any
from enum import Enum

class AssetType(str, Enum):
    SOURCE = "source"
    FEEDER = "feeder"
    SERVICE = "service"
    HOSPITAL_ROOM = "hospital_room"
    CLASSROOM = "classroom"
    LOAD = "load"
    TRANSFORMER = "transformer"

class Tier(str, Enum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"

class Coordinates(BaseModel):
    x: float
    y: float

class Asset(BaseModel):
    id: str
    type: AssetType
    name: str
    parent_id: Optional[str] = None
    capacity_w: Optional[int] = Field(None, ge=0)
    rating_w: Optional[int] = Field(None, ge=0)
    tier: Optional[Tier] = None
    zone: Optional[str] = None
    led_bit: Optional[int] = None
    coords: Optional[Coordinates] = None
    policy_refs: Optional[List[str]] = None
    essential: Optional[bool] = None

class SiteProfile(BaseModel):
    version: str
    name: str
    assets: List[Asset]

    @model_validator(mode='after')
    def validate_topology(self):
        assets = self.assets
        asset_dict = {}
        for a in assets:
            if a.id in asset_dict:
                raise ValueError(f"Duplicate Asset ID: {a.id}")
            asset_dict[a.id] = a

        # Dangling IDs and connectivity
        for asset in assets:
            if asset.parent_id is not None:
                if asset.parent_id not in asset_dict:
                    raise ValueError(f"Dangling parent_id: {asset.parent_id} for asset {asset.id}")

        # Check for cycles
        for asset in assets:
            visited = set()
            curr = asset
            while curr.parent_id:
                if curr.id in visited:
                    raise ValueError(f"Cycle detected involving asset {curr.id}")
                visited.add(curr.id)
                curr = asset_dict[curr.parent_id]

        # Conflicting parent/child accounting
        parent_totals = {}
        for asset in assets:
            if asset.parent_id:
                val = asset.rating_w or asset.capacity_w or 0
                if asset.type == AssetType.TRANSFORMER: continue # Transformers don't add to electrical loads in this demo
                if asset.type == AssetType.HOSPITAL_ROOM: continue # Hospital rooms don't define wattage
                parent_totals[asset.parent_id] = parent_totals.get(asset.parent_id, 0) + val

        for pid, total in parent_totals.items():
            parent = asset_dict[pid]
            limit = parent.capacity_w or parent.rating_w
            if limit is not None and total > limit:
                raise ValueError(f"Asset {pid} capacity {limit} exceeded by children total {total}")
        return self

class RfidEnrollment(BaseModel):
    tag_to_room: Dict[str, str]

def load_site_profile(path: str) -> SiteProfile:
    with open(path, "r") as f:
        data = json.load(f)
    return SiteProfile(**data)

def load_rfid_enrollment(path: str) -> RfidEnrollment:
    with open(path, "r") as f:
        data = json.load(f)
    return RfidEnrollment(**data)


import hashlib
def get_config_hash(profile: SiteProfile) -> str:
    # Hash the JSON representation of the config to ensure deterministic runs
    data = profile.model_dump_json()
    return hashlib.sha256(data.encode('utf-8')).hexdigest()[:8]
