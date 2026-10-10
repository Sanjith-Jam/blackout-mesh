import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from app.district.authority import DistrictAuthority


class DistrictActionName(StrEnum):
    inject_fault = "inject_fault"
    clear_fault = "clear_fault"
    propose_recovery = "propose_recovery"
    apply_recovery = "apply_recovery"
    advance_hour = "advance_hour"
    transformer_scenario = "transformer_scenario"
    reset = "reset"


class DistrictAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: StrictStr
    expected_revision: StrictInt = Field(ge=1)
    action: DistrictActionName = Field(strict=False)
    component_id: StrictStr | None = None
    fault_kind: StrictStr | None = None


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: StrictStr
    expected_revision: StrictInt = Field(ge=1)
    cluster_count: StrictInt = Field(ge=2, le=6)
    secondary_strategy: StrictStr


class DistrictSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: StrictStr
    identity: "DistrictIdentity"
    profile: "DistrictProfileInfo"
    site: "DistrictSite"
    map: "DistrictMap"
    topology: "DistrictTopology"
    generation: "DistrictGeneration"
    state: "DistrictState"
    energy: "DistrictEnergy"


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DistrictIdentity(StrictDTO):
    site_id: StrictStr
    run_id: StrictStr
    revision: StrictInt
    server_epoch: StrictStr
    profile_hash: StrictStr


class DistrictDispatch(StrictDTO):
    solver: StrictStr
    status: StrictStr
    validation: StrictStr
    physical_confirmation: None


class DistrictProfileInfo(StrictDTO):
    id: StrictStr
    config_hash: StrictStr
    demand_basis: StrictStr
    local_supply_mode: StrictStr
    catalog_version: StrictStr | None
    catalog_hash: StrictStr | None
    appliance_count: StrictInt
    decision: DistrictDispatch


class DistrictAppliance(StrictDTO):
    id: StrictStr
    service_id: StrictStr
    room_id: StrictStr
    rated_max_w: StrictInt
    requested_w: StrictInt
    served_w: StrictInt
    priority_class: StrictStr
    reachable: StrictBool
    path_edge_ids: list[StrictStr]


class DistrictSite(StrictDTO):
    name: StrictStr
    center: dict
    radius_m: StrictInt


class DistrictPath(StrictDTO):
    coordinates: list[list[StrictFloat]]


class DistrictMapFeature(StrictDTO):
    id: StrictStr
    kind: StrictStr
    name: StrictStr | None
    geometry_type: StrictStr
    paths: list[DistrictPath]


class DistrictMap(StrictDTO):
    radius_m: StrictInt
    source: StrictStr
    source_url: StrictStr
    attribution: StrictStr
    license: StrictStr
    retrieved: StrictStr
    source_sha256: StrictStr
    features: list[DistrictMapFeature]


class DistrictTopology(StrictDTO):
    schema_version: StrictStr
    engine: StrictStr
    engine_version: StrictStr
    engine_license: StrictStr
    secondary_strategy: StrictStr
    cluster_count: StrictInt
    group_members: dict[str, list[StrictStr]]
    provenance: StrictStr
    equipment_stage: StrictStr
    nodes: list[dict]
    edges: list[dict]


class DistrictGeneration(StrictDTO):
    status: StrictStr
    available: StrictBool
    cluster_count: StrictInt | None
    secondary_strategy: StrictStr | None
    reason: StrictStr | None
    generated_at: StrictStr | None


class DistrictLoad(StrictDTO):
    appliances: list[DistrictAppliance]
    building_id: StrictStr
    tier: StrictStr
    tier_provenance: StrictStr
    tier_rationale: StrictStr
    requested_w: StrictInt
    local_supply_w: StrictInt
    grid_requested_w: StrictInt
    grid_served_w: StrictInt
    served_w: StrictInt
    unmet_w: StrictInt
    demand_provenance: StrictStr
    local_supply_provenance: StrictStr
    local_supply_basis: StrictStr
    local_supply_semantics: StrictStr
    grid_service_provenance: StrictStr
    unmet_provenance: StrictStr


class DistrictEnergyHour(StrictDTO):
    hour: StrictInt
    demand_w: StrictInt
    pv_w: StrictInt
    baseline_grid_w: StrictInt
    dispatch_grid_w: StrictInt
    battery_soc_wh: StrictInt
    pv_used_w: StrictInt
    battery_charge_w: StrictInt
    battery_discharge_w: StrictInt
    grid_import_w: StrictInt
    loss_wh: StrictInt


class DistrictState(StrictDTO):
    hour: StrictInt
    source_capacity_w: StrictInt
    source_capacity_provenance: StrictStr
    source_capacity_note: StrictStr
    grid_requested_w: StrictInt
    grid_served_w: StrictInt
    unmet_w: StrictInt
    source_available: StrictBool
    edges: list[dict]
    loads: list[DistrictLoad]
    critical_shortfall_w: StrictInt
    faults: list[dict]
    restoration: dict
    transformers: list[dict]


class DistrictEnergyTotals(StrictDTO):
    period_hours: StrictInt
    demand_wh: StrictInt
    pv_generated_wh: StrictInt
    pv_used_wh: StrictInt
    pv_curtailed_wh: StrictInt
    baseline_import_scheduled_wh: StrictInt
    dispatch_import_scheduled_wh: StrictInt
    grid_export_wh: StrictInt
    battery_charge_wh: StrictInt
    battery_discharge_wh: StrictInt
    battery_loss_wh: StrictInt
    battery_round_trip_efficiency: StrictFloat


class DistrictNetworkEnergyInterval(StrictDTO):
    duration_hours: StrictInt
    requested_wh: StrictInt
    local_supply_wh: StrictInt
    grid_import_requested_wh: StrictInt
    grid_served_wh: StrictInt
    served_wh: StrictInt
    unmet_wh: StrictInt
    unmet_fraction_of_requested: StrictFloat


class DistrictEnergy(StrictDTO):
    hour: StrictInt
    profile: list[DistrictEnergyHour]
    battery_soc_wh: StrictInt
    engine: StrictStr
    provenance: StrictStr
    pv_used_w: StrictInt
    battery_charge_w: StrictInt
    battery_discharge_w: StrictInt
    grid_import_w: StrictInt
    totals: DistrictEnergyTotals
    network_interval: DistrictNetworkEnergyInterval


def register_district():
    router = APIRouter(prefix="/api/v1/district", tags=["district study"])

    @router.get("", response_model=DistrictSnapshot)
    async def district_snapshot(request: Request):
        async with request.app.state.district_lock:
            return await asyncio.to_thread(request.app.state.district.snapshot)

    @router.post("/action", response_model=DistrictSnapshot)
    async def district_action(body: DistrictAction, request: Request):
        async with request.app.state.district_lock:
            district: DistrictAuthority = request.app.state.district
            if body.run_id != district.run_id or body.expected_revision != district.revision:
                raise HTTPException(409, "district run or revision is stale")
            if district.generation.get("status") == "GENERATING" and body.action != DistrictActionName.reset:
                raise HTTPException(409, "district topology generation is in progress")
            result = await asyncio.to_thread(district.apply_action, body)
            if not result:
                raise HTTPException(422, "action is invalid for the current district state")
            district.revision += 1
            return await asyncio.to_thread(district.snapshot)

    @router.post("/generation", response_model=DistrictSnapshot)
    async def generate_topology(body: GenerationRequest, request: Request):
        async with request.app.state.district_lock:
            district: DistrictAuthority = request.app.state.district
            if body.run_id != district.run_id or body.expected_revision != district.revision:
                raise HTTPException(409, "district run or revision is stale")
            if body.secondary_strategy not in {"RadialStrategy", "MeshSteinerStrategy"}:
                raise HTTPException(422, "unsupported SHIFT secondary strategy")
            if district.generation.get("status") == "GENERATING":
                raise HTTPException(409, "topology generation is already running")
            python = Path(__file__).resolve().parents[3] / ".venv-city/bin/python"
            script = Path(__file__).resolve().parents[2] / "scripts/generate_district_topology.py"
            if not district.generation["available"] or not python.is_file():
                district.revision += 1
                district.generation.update(status="UNAVAILABLE", available=False,
                    reason="Optional SHIFT runtime is unavailable; cached topology remains active.")
                return await asyncio.to_thread(district.snapshot)
            district.generation.update(status="GENERATING", available=True,
                cluster_count=body.cluster_count, secondary_strategy=body.secondary_strategy,
                reason=None, generated_at=None)
            task_id = district.generation_task_id = str(uuid.uuid4())
            run_id = district.run_id
            district.revision += 1
            revision = district.revision
            asyncio.create_task(_run_generation(district, python, script, body, run_id, task_id, revision, request.app.state.district_lock))
            return await asyncio.to_thread(district.snapshot)

    return router


def initialize_district(app):
    app.state.district = DistrictAuthority()
    app.state.district_lock = asyncio.Lock()


async def _run_generation(district, python, script, body, run_id, task_id, revision, lock=None):
    lock = lock or asyncio.Lock()
    def current_job():
        return district.run_id == run_id and district.generation_task_id == task_id and district.revision == revision

    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="district-topology-", suffix=".json")
        os.close(fd)
        proc = await asyncio.create_subprocess_exec(str(python), str(script), "--clusters",
            str(body.cluster_count), "--secondary-strategy", body.secondary_strategy,
            "--output", temp_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError("SHIFT generation exceeded 10 second limit")
        if proc.returncode:
            raise RuntimeError(stderr.decode("utf-8", "replace")[-1000:] or "SHIFT generation failed")
        result = json.loads(Path(temp_path).read_text())
        nodes, edges = result.get("nodes", []), result.get("edges", [])
        node_ids = {node.get("id") for node in nodes}
        if len(nodes) > 500 or len(edges) > 1000:
            raise RuntimeError("generated topology exceeds bounded graph size")
        if not nodes or len(node_ids) != len(nodes) or any(edge.get("from") not in node_ids or edge.get("to") not in node_ids for edge in edges):
            raise RuntimeError("generated topology has missing or duplicate node IDs")
        tree_edges = [edge for edge in edges if edge.get("kind") != "tie"]
        if len(tree_edges) != len(nodes) - 1:
            raise RuntimeError("generated primary topology is not a tree")
        reached = set()
        adjacency = {}
        for edge in tree_edges:
            adjacency.setdefault(edge["from"], set()).add(edge["to"])
            adjacency.setdefault(edge["to"], set()).add(edge["from"])
        queue = [next((node["id"] for node in nodes if node.get("role") == "source"), None)]
        queue = [node for node in queue if node]
        while queue:
            node = queue.pop()
            if node in reached:
                continue
            reached.add(node)
            queue.extend(adjacency.get(node, set()) - reached)
        if reached != node_ids:
            raise RuntimeError("generated primary topology is disconnected")
        async with lock:
            if not current_job():
                return
            district.profile.validate_topology(result)
            district.topology = result
            district.generation.update(status="GENERATED", cluster_count=body.cluster_count,
                secondary_strategy=body.secondary_strategy, generated_at=datetime.now(timezone.utc).isoformat(),
                reason=None)
            district.revision += 1
    except Exception as exc:
        async with lock:
            if current_job():
                district.generation.update(status="FAILED", reason=f"{type(exc).__name__}: {exc}", generated_at=None)
                district.revision += 1
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
