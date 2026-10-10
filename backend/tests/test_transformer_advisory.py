from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.diagnosis.transformer_advisory import advise, features_at

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def history():
    return [dict(transformer_id="TX1", recorded_at=NOW-timedelta(hours=719-i),
                 status="SIMULATED", load_percentage=50+i/10,
                 oil_temperature_c=60, ambient_temp_c=25, power_factor=.9,
                 harmonic_distortion=2, age_years=5, capacity_kva=100,
                 is_fault_event=False, fault_event_provenance="OBSERVED_TRIP")
            for i in range(720)]


def test_causal_windows_and_advisory_gate():
    rows = history()
    before = advise(rows, "TX1", NOW)
    assert before["status"] == "UNKNOWN"
    assert before["failure_probability"] is None
    f = before["features"]
    assert len(f) == 20
    assert f["load_7d_mean"] == pytest.approx(sum(r["load_percentage"] for r in rows[-168:])/168)
    changed = deepcopy(rows)
    for r in changed:
        r.update(scenario="failure", will_fail_30d=1, topology_truth=False,
                 allocator_mask=0, post_restoration_outcome=999)
    changed += [dict(rows[-1], recorded_at=NOW+timedelta(hours=1), oil_temperature_c=240),
                dict(rows[-1], transformer_id="OTHER", oil_temperature_c=240)]
    assert advise(changed, "TX1", NOW) == before
    assert rows == history()


@pytest.mark.parametrize("field,value", [("oil_temperature_c", None),
    ("power_factor", float("nan")), ("load_percentage", 201),
    ("capacity_kva", True), ("status", "STALE"),
    ("fault_event_provenance", "SCENARIO_LABEL"), ("is_fault_event", 1)])
def test_invalid_abstains(field, value):
    rows = history()
    rows[-1][field] = value
    result = advise(rows, "TX1", NOW)
    assert result["status"] == "UNKNOWN" and result["features"] is None


def test_missing_duplicate_irregular_and_stale():
    rows = history()
    assert features_at(rows[:-1], "TX1", NOW)[0] is None
    rows[10]["recorded_at"] = rows[9]["recorded_at"]
    assert features_at(rows, "TX1", NOW)[1] == "UNSUPPORTED_CADENCE"
    assert features_at(history(), "TX1", NOW+timedelta(hours=2))[0] is None


def test_advisory_cannot_mutate_district_controls(monkeypatch):
    from app.district import authority
    monkeypatch.setattr(authority, "shift_runtime_probe", lambda: (False, "test"))
    district = authority.DistrictAuthority()
    before = district.snapshot()
    advise(history(), "TX1", NOW)
    assert district.snapshot() == before
    assert district.closed_tie is None and district.candidate_tie is None
