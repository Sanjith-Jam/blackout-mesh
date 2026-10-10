import json

import pytest
from pydantic import ValidationError

from app.district.authority import DATA, DistrictAuthority
from app.district.profile import DistrictProfile, apportion, load_profile


def test_explicit_profiles_reject_missing_duplicate_and_invalid_buildings(tmp_path):
    district = DistrictAuthority()
    profile = json.loads((DATA / "gnitc_profile.json").read_text())
    for field, value in (("source_capacity_w", True), ("source_capacity_w", 1.5),
                         ("local_supply_mode", "invent_islands")):
        with pytest.raises(ValidationError):
            DistrictProfile.model_validate({**profile, field: value})
    with pytest.raises(ValidationError):
        DistrictProfile.model_validate({**profile, "buildings": profile["buildings"] * 2})
    profile["buildings"].pop()
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="building mismatch"):
        load_profile(path, district.topology)


def test_integer_weighted_demand_conserves_power_and_is_independent_of_input_order():
    for total in range(25):
        weights = {"a": 5, "b": 2, "c": 0}
        result = apportion(total, weights)
        assert sum(result.values()) == total and result["c"] == 0
        assert result == apportion(total, dict(reversed(list(weights.items()))))
    with pytest.raises(ValueError):
        apportion(5, {"a": 0})


def test_configured_tiers_and_weights_drive_snapshot(tmp_path, monkeypatch):
    profile = json.loads((DATA / "gnitc_profile.json").read_text())
    for row in profile["buildings"]:
        row.update(tier="noncritical", demand_weight=0)
    target = profile["buildings"][-1]
    target.update(tier="critical", demand_weight=1, rationale="Explicit test policy")
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile))
    monkeypatch.setenv("DISTRICT_PROFILE", str(path))
    district = DistrictAuthority()
    loads = district.snapshot()["state"]["loads"]
    assert loads[0]["building_id"] == target["building_id"]
    assert loads[0]["tier_rationale"] == "Explicit test policy"
    assert loads[0]["requested_w"] == district.energy_trace["profile"][12]["demand_w"]
    assert sum(load["requested_w"] for load in loads[1:]) == 0
