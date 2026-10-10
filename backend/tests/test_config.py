"""Site profiles (#26): strict validation with actionable diagnostics before anything is activated."""
import copy
import json
from pathlib import Path

import pytest

from app.core.config import (Asset, AssetType, SiteProfile, SiteProfileError, build_catalog, get_config_hash,
                             load_rfid_enrollment, load_site_profile, parse_site_profile)

SITES = Path(__file__).resolve().parents[1] / "sites"
DEFAULT = json.loads((SITES / "default_campus.json").read_text())


def test_duplicate_ids():
    with pytest.raises(ValueError, match="Duplicate Asset ID"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="A", type=AssetType.SOURCE, name="S1"),
                Asset(id="A", type=AssetType.FEEDER, name="F1", parent_id="A")
            ]
        )

def test_dangling_parent():
    with pytest.raises(ValueError, match="Dangling parent_id: INVALID"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="S1", type=AssetType.SOURCE, name="S1"),
                Asset(id="F1", type=AssetType.FEEDER, name="F1", parent_id="INVALID")
            ]
        )

def test_cycle():
    with pytest.raises(ValueError, match="Cycle detected"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="A", type=AssetType.FEEDER, name="A", parent_id="B"),
                Asset(id="B", type=AssetType.FEEDER, name="B", parent_id="A")
            ]
        )

def test_capacity_exceeded():
    with pytest.raises(ValueError, match="Asset S1 capacity 100 exceeded by children total 150"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="S1", type=AssetType.SOURCE, name="S1", capacity_w=100),
                Asset(id="F1", type=AssetType.FEEDER, name="F1", parent_id="S1", capacity_w=75),
                Asset(id="F2", type=AssetType.FEEDER, name="F2", parent_id="S1", capacity_w=75)
            ]
        )


@pytest.mark.parametrize("path", sorted(SITES.glob("*_site.json")) + [SITES / "default_campus.json"],
                         ids=lambda p: p.name)
def test_shipped_profiles_validate(path):
    catalog = build_catalog(load_site_profile(str(path)))
    assert catalog.services and catalog.classrooms and catalog.hospital_zones


def test_two_sites_differ_in_rooms_and_loads():
    campus = build_catalog(load_site_profile(str(SITES / "default_campus.json")))
    small = build_catalog(load_site_profile(str(SITES / "small_test_site.json")))
    assert len(campus.classrooms) != len(small.classrooms)
    assert len(campus.hospital_zones) != len(small.hospital_zones)
    assert len(campus.services) != len(small.services)
    assert campus.config_hash != small.config_hash


def test_default_profile_reproduces_the_reference_catalog():
    catalog = build_catalog(load_site_profile(str(SITES / "default_campus.json")))
    assert [(s["id"], s["feeder"], s["tier"], s["watts"]) for s in catalog.services] == [
        ("L0", "A", "T1", 2000), ("L1", "A", "T1", 1000), ("L2", "A", "T2", 3000),
        ("L3", "B", "T2", 2000), ("L4", "B", "T2", 2000), ("L5", "B", "T3", 4000)]
    assert catalog.source_capacity_w == 14000 and catalog.feeder_limits_w == {"A": 6000, "B": 8000}
    assert catalog.hospital_zones == ("ICU", "Theatre", "Wards")
    assert catalog.protected_services == ("L0", "L1")
    assert {c["id"]: (c["led_bit"], c["hardware_room"]) for c in catalog.classrooms} == {
        "CR1": (3, "A"), "CR2": (4, "B"), "CR3": (5, "C")}
    assert sum(w for rows in catalog.hospital_loads.values() for _, _, w, _ in rows) == 6000


def test_config_hash_is_stable_and_tracks_content():
    profile = parse_site_profile(json.dumps(DEFAULT))
    assert get_config_hash(profile) == get_config_hash(parse_site_profile(json.dumps(DEFAULT, indent=4)))
    changed = copy.deepcopy(DEFAULT)
    changed["name"] = "Renamed"
    assert get_config_hash(parse_site_profile(json.dumps(changed))) != get_config_hash(profile)


def asset(data, asset_id):
    return next(a for a in data["assets"] if a["id"] == asset_id)


def mutate(fn):
    data = copy.deepcopy(DEFAULT)
    fn(data)
    return data


INVALID = {
    "duplicate id": (lambda d: d["assets"].append(dict(asset(d, "CR1"))), "Duplicate Asset ID: CR1"),
    "dangling parent": (lambda d: asset(d, "L3").update(parent_id="C"), "Dangling parent_id: C for asset L3"),
    "transformer in watts": (lambda d: asset(d, "TX1").update(rating_w=100), "TX1: rating_w is not allowed (transformer ratings are amps"),
    "fractional watts": (lambda d: asset(d, "L3").update(rating_w=2000.5), "L3.rating_w"),
    "watts as text": (lambda d: asset(d, "L3").update(rating_w="2000"), "L3.rating_w"),
    "negative watts": (lambda d: asset(d, "L_CR1_fans").update(rating_w=-100), "L_CR1_fans.rating_w"),
    "unknown field": (lambda d: asset(d, "L3").update(rating_kw=2), "L3.rating_kw"),
    "service on wrong feeder": (lambda d: asset(d, "L3").update(parent_id="A"), "L3: classroom services belong on feeder B"),
    "load under feeder": (lambda d: asset(d, "L_CR1_fans").update(parent_id="B"), "L_CR1_fans: a load must sit under a classroom or transformer"),
    "leaves do not reconcile": (lambda d: asset(d, "L_CR1_ac").update(rating_w=900), "L3: leaf loads total 1900 W but the service is rated 2000 W"),
    "essential on T2 service": (lambda d: asset(d, "L_TX2_ac").update(essential=True), "L_TX2_ac: essential=True but L2 is T2"),
    "hospital load without service": (lambda d: asset(d, "L_TX1_monitor").pop("service_id"), "L_TX1_monitor: hospital loads need service_id"),
    "shared LED bit": (lambda d: asset(d, "CR2").update(led_bit=3), "CR2: led_bit 3 already used by CR1"),
    "LED bit out of range": (lambda d: asset(d, "CR2").update(led_bit=9), "CR2.led_bit"),
    "impossible feeder rating": (lambda d: asset(d, "B").update(capacity_w=9000), "Asset SOURCE capacity 14000 exceeded by children total 15000"),
    "unknown fault zone": (lambda d: d.update(fault_zone="Lobby"), "fault_zone 'Lobby' is not a transformer zone"),
    "missing tier": (lambda d: asset(d, "L2").pop("tier"), "L2: service requires tier"),
}


@pytest.mark.parametrize("case", INVALID, ids=list(INVALID))
def test_invalid_profiles_fail_with_actionable_diagnostics(case):
    fn, expected = INVALID[case]
    with pytest.raises(SiteProfileError) as err:
        parse_site_profile(json.dumps(mutate(fn)), "bad.json")
    assert any(expected in line for line in err.value.problems), err.value.problems
    assert "bad.json" in str(err.value)


def test_every_problem_is_reported_at_once():
    def two(d):
        asset(d, "L_CR1_ac").update(rating_w=900)
        asset(d, "CR2").update(led_bit=3)
    with pytest.raises(SiteProfileError) as err:
        parse_site_profile(json.dumps(mutate(two)))
    assert len(err.value.problems) == 2


def test_rfid_enrollment_prefers_the_untracked_local_file(tmp_path):
    tracked = tmp_path / "rfid_enrollment.json"
    tracked.write_text(json.dumps({"tag_to_room": {"CARD_1_UID": "CR1"}}))
    assert load_rfid_enrollment(str(tracked)).tag_to_room == {"CARD_1_UID": "CR1"}
    (tmp_path / "rfid_enrollment.local.json").write_text(json.dumps({"tag_to_room": {"04A1B2C3": "CR2"}}))
    assert load_rfid_enrollment(str(tracked)).tag_to_room == {"04A1B2C3": "CR2"}
