from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional, Any
from enum import Enum

class AssetType(str, Enum):
    SOURCE = "source"
    FEEDER = "feeder"
    SERVICE = "service"
    ROOM = "room"
    CLASSROOM = "classroom"
    HOSPITAL_ROOM = "hospital_room"

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
        
        return self

class RfidEnrollment(BaseModel):
    # maps raw RFID tag uid to a classroom alias/ID
    tag_to_room: Dict[str, str]
