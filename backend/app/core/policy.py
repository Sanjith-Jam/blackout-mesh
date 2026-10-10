"""Versioned soft preferences; protected services and physical limits are not configurable."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt

class AllocationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: Literal["activity_first", "water_first"] = "activity_first"
    version: Literal["allocation-v1"] = "allocation-v1"
    fairness_weight: StrictInt = Field(default=0, ge=0, le=100)
    switching_penalty: StrictInt = Field(default=1, ge=0, le=100)

    @property
    def objective_order(self):
        soft = ["active", "unknown", "water", "inactive"]
        if self.name == "water_first":
            soft = ["water", "active", "unknown", "inactive"]
        return ["protected", *soft, "fairness", "switching", "served_w", "deterministic_mask"]


def score(mask, services, activity, previous_mask, policy, waiting_s):
    on = lambda i: int(bool(mask & (1 << i)))
    protected = tuple(on(i) for i, svc in enumerate(services) if svc["tier"] == "T1")
    terms = {state.lower(): sum(on(i) for i, svc in enumerate(services)
                  if svc.get("zone") == "classroom" and activity.get(svc.get("classroom_id", f"CR{i - 2}"), {}).get("state", "UNKNOWN") == state)
             for state in ("ACTIVE", "UNKNOWN", "INACTIVE")}
    terms.update(water=sum(on(i) for i, svc in enumerate(services) if svc.get("zone") == "water"),
                 fairness=policy.fairness_weight * sum(on(i) * min(3600, int(waiting_s.get(svc["id"], 0)))
                            for i, svc in enumerate(services) if svc["tier"] != "T1"),
                 switching=-policy.switching_penalty * (mask ^ previous_mask).bit_count(),
                 served_w=sum(svc["watts"] for i, svc in enumerate(services) if on(i)), deterministic_mask=-mask)
    return protected + tuple(terms[k] for k in policy.objective_order[1:]), {"protected": list(protected), **terms}
