"""A second site runs from configuration only (#26): no source edits, its own counts and config hash."""
import json
import os
import subprocess
import sys
from pathlib import Path

from sqlmodel import Session, select

import app.main as main
from app.core.active_site import CATALOG
from app.storage.models import Decision

BACKEND = Path(__file__).resolve().parents[1]
SMALL = BACKEND / "sites" / "small_test_site.json"

# Runs in a fresh interpreter: the active profile is chosen once, at import, like a server restart.
PROBE = r"""
import json
from fastapi.testclient import TestClient
import app.main as main
from app.core.site import reconcile_catalog
from app.storage.models import Decision
from sqlmodel import Session, select

with TestClient(main.app) as client:
    snap = client.get("/api/v1/snapshot").json()
    classrooms = client.get("/api/v1/visualizers/classrooms").json()
    hospital = client.get("/api/v1/visualizers/hospital").json()
    short = client.post("/api/v1/visualizers/classrooms", json={"action": "overload"}).json()
    fault = client.post("/api/v1/visualizers/hospital", json={"action": "inject_fault", "fault": "overload"})
    bad_zone = client.post("/api/v1/visualizers/hospital", json={"action": "scan", "zone_id": "ICU"})
    with Session(main.app.state.grid.storage.engine) as session:
        hashes = sorted({d.context.get("config_hash") for d in session.exec(select(Decision)).all()})
print(json.dumps({
    "reconcile": reconcile_catalog(),
    "site": snap["site"], "identity_hash": snap["contract"]["identity"]["config_hash"],
    "services": [(s["id"], s["feeder"], s["watts"]) for s in snap["services"]],
    "modeled_mask": snap["modeled_mask"],
    "rooms": [r["id"] for r in classrooms["rooms"]], "classroom_requested_w": classrooms["requested_w"],
    "classroom_range_w": classrooms["capacity_range_w"], "shortage_capacity_w": short["capacity_w"],
    "short_served": sorted((r["id"], l["id"]) for r in short["rooms"] for l in r["loads"] if l["served"]),
    "transformers": [(t["id"], t["zone"]) for t in hospital["transformers"]],
    "hospital_requested_w": hospital["requested_w"],
    "fault_status": fault.status_code, "bad_zone_status": bad_zone.status_code, "decision_hashes": hashes,
}))
"""


def run_site(profile, tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "SITE_PROFILE": str(profile), "PYTHONPATH": str(BACKEND),
           "DATABASE_URL": f"sqlite:///{tmp_path / 'audit.sqlite3'}",
           "PRIORITYGRID_HISTORY_DB": str(tmp_path / "history.sqlite3")}
    out = subprocess.run([sys.executable, "-c", PROBE], env=env, cwd=tmp_path, capture_output=True, text=True,
                         timeout=180)
    assert out.returncode == 0, out.stderr[-3000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_small_site_runs_from_configuration_only(tmp_path):
    first = run_site(SMALL, tmp_path / "a")
    assert first["reconcile"] == []
    assert first["site"]["site_name"] == "Small Test Site"
    assert first["site"]["config_hash"] == first["identity_hash"]
    assert first["decision_hashes"] == [first["identity_hash"]]
    assert first["services"] == [["S0", "A", 1200], ["S1", "A", 800], ["S2", "B", 1800], ["S3", "B", 1200]]
    assert first["modeled_mask"] == 0b1111
    assert first["rooms"] == ["LAB", "SEM"] and first["classroom_requested_w"] == 3000
    assert first["classroom_range_w"] == [0, 3500] and first["shortage_capacity_w"] == 2000
    assert first["transformers"] == [["TXC", "Clinic"], ["TXP", "Pharmacy"]]
    assert first["hospital_requested_w"] == 2000
    assert first["fault_status"] == 200
    assert first["bad_zone_status"] == 422  # the default campus's zones are not this site's
    # Essentials first under the 2,000 W shortage preset: lighting + computers (1,100 W), then optional loads.
    served = {tuple(x) for x in first["short_served"]}
    assert {("LAB", "lighting"), ("LAB", "computers"), ("SEM", "lighting")} <= served
    # Same profile, fresh process: the same allocation and projections.
    second = run_site(SMALL, tmp_path / "b")
    for key in ("services", "modeled_mask", "rooms", "short_served", "transformers", "identity_hash"):
        assert first[key] == second[key]


def test_decisions_record_the_active_config_hash():
    grid = main.app.state.grid
    with Session(grid.storage.engine) as session:
        decisions = session.exec(select(Decision)).all()
    assert decisions
    assert {d.context["config_hash"] for d in decisions} == {CATALOG.config_hash}
    assert grid.identity()["config_hash"] == CATALOG.config_hash
