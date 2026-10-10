"""Strict, explicit synthetic district policy; missing buildings never inherit an ID-based tier."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator


class BuildingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    building_id: StrictStr
    tier: Literal["critical", "noncritical"]
    rationale: StrictStr = Field(min_length=1)
    demand_weight: StrictInt = Field(ge=0, le=1_000_000)
    room_id: StrictStr | None = None


class DistrictProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal["district-profile-v1"]
    id: StrictStr = Field(min_length=1)
    provenance: Literal["CONFIGURED_SIMULATED_ASSUMPTION"]
    source_capacity_w: StrictInt = Field(ge=0, le=1_000_000)
    # Declared headroom for series losses so a full dispatch still fits the source after AC losses.
    loss_reserve_w: StrictInt = Field(default=0, ge=0, le=100_000)
    demand_basis: Literal["hourly_trace_weights", "appliance_inventory"]
    local_supply_mode: Literal["grid_following", "disabled"]
    buildings: list[BuildingPolicy]
    appliance_requests_w: dict[StrictStr, StrictInt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_buildings(self):
        if self.loss_reserve_w > self.source_capacity_w:
            raise ValueError("loss reserve cannot exceed source capacity")
        ids = [row.building_id for row in self.buildings]
        rooms = [row.room_id for row in self.buildings if row.room_id is not None]
        if not ids or len(ids) != len(set(ids)) or len(rooms) != len(set(rooms)):
            raise ValueError("building and mapped room identities must be unique and nonempty")
        if self.demand_basis == "hourly_trace_weights" and (rooms or not any(row.demand_weight for row in self.buildings)):
            raise ValueError("hourly trace requires positive weights and no appliance mappings")
        if self.demand_basis == "appliance_inventory" and (self.local_supply_mode != "disabled" or any(row.demand_weight for row in self.buildings)):
            raise ValueError("appliance study requires disabled DER and zero aggregate weights")
        if self.demand_basis == "hourly_trace_weights" and self.appliance_requests_w:
            raise ValueError("hourly trace cannot also request appliances")
        return self

    @property
    def config_hash(self):
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def validate_topology(self, topology):
        actual = {node.get("building_id", node["id"]) for node in topology["nodes"] if node["role"] == "load"}
        configured = {row.building_id for row in self.buildings}
        if actual != configured:
            raise ValueError(f"district profile building mismatch: missing={sorted(actual-configured)}, extra={sorted(configured-actual)}")


def load_profile(path: Path, topology) -> DistrictProfile:
    profile = DistrictProfile.model_validate_json(path.read_text(encoding="utf-8"))
    profile.validate_topology(topology)
    return profile


def apportion(total_w: int, weights: dict[str, int]) -> dict[str, int]:
    """Largest remainders conserve integer W; asset IDs only resolve equal remainders."""
    if type(total_w) is not int or total_w < 0 or any(type(w) is not int or w < 0 for w in weights.values()):
        raise ValueError("nonnegative integer watts/weights required")
    denominator = sum(weights.values())
    if not denominator:
        if total_w:
            raise ValueError("positive demand requires configured weights")
        return dict.fromkeys(weights, 0)
    result = {key: total_w * weight // denominator for key, weight in weights.items()}
    order = sorted(weights, key=lambda key: (-(total_w * weights[key] % denominator), key))
    for key in order[:total_w - sum(result.values())]:
        result[key] += 1
    return result
