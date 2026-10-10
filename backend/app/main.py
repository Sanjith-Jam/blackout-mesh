import asyncio
import json
import math
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Request, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Literal
from pydantic import BaseModel, ConfigDict, StrictInt

from app.schemas.snapshot import (
    HealthResponse, ModelStatusResponse, ActivityObservationResponse, ReplayActionResponse, CrossRouteContract,
    WebSocketMessageEnvelope, HardwareAckRequest, HardwareAckResponse,
    SystemSnapshot,
    RfidScanRequest,
    RfidScanResponse,
    RfidEventType,
    CapacityChangeRequest,
    CapacityChangeResponse,
    ClassroomLoadRequest,
    ClassroomLoadResponse,
    FeederChangeRequest,
    FeederChangeResponse,
    ActivityObservationRequest,
    ReplayActionRequest,
)
from app.core.state import GridState
from app.core.control_loop import ControlLoop
from app.core.site import SiteAuthority
from app.core.policy import AllocationPolicy
from app.simulation.electrical import ElectricalInput, ElectricalStudyResponse, solve as solve_electrical, diagnose_study
from app.activity.model import FEATURES
from app.visualizers import CAPACITY_RANGE_W as CLASSROOM_CAPACITY_RANGE_W, ClassroomDemo, HospitalPriorityDemo, hospital_snapshot

class ClassroomDemoAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["scan", "unscan", "set_capacity", "normal", "overload", "reset",
                    "replay_pause", "replay_resume", "replay_step"]
    classroom_id: Literal["CR1", "CR2", "CR3"] | None = None
    capacity_w: StrictInt | None = None

class HospitalDemoAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["scan", "unscan", "set_capacity", "normal", "overload", "reset", "replay_pause", "replay_resume", "replay_step"] | None = None
    zone_id: Literal["ICU", "Theatre", "Wards"] | None = None
    capacity_w: StrictInt | None = None
    scenario: Literal["normal", "overload", "cooling_failure", "upstream_loss", "missing_sensor"] | None = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


def load_replay():
    try:
        data = json.loads(REPLAY_PATH.read_text())
        return {cid: rows for cid, rows in data.items() if cid in ("CR1", "CR2", "CR3") and isinstance(rows, list)}
    except (OSError, ValueError):
        return {}

def with_site(data: dict, identity: dict) -> dict:
    data = dict(data)
    data["site"] = identity
    return data

REPLAY_PATH = Path(__file__).resolve().parents[1] / "models" / "replay.json"


def initialize_state(app: FastAPI):
    app.state.manager = ConnectionManager()
    app.state.replay_data = load_replay()
    app.state.grid = GridState()
    app.state.grid.replay_length = max((len(rows) for rows in app.state.replay_data.values()), default=0)
    app.state.classroom_demo = ClassroomDemo(model=app.state.grid.model, replay=app.state.replay_data)
    app.state.hospital_demo = HospitalPriorityDemo(model=app.state.grid.model, replay=app.state.replay_data)
    app.state.site = SiteAuthority(app.state.grid, app.state.classroom_demo, app.state.hospital_demo)
    app.state.replay_generation = 0
    app.state.replay_task = None
    app.state.electrical_study_lock = asyncio.Lock()
    async def publish():
        if app.state.manager.active_connections:
            snapshot = campus_snapshot(app.state.site)
            await app.state.manager.broadcast(socket_payload(snapshot, app.state.site))
    app.state.control_loop = ControlLoop([app.state.site.tick], publish=publish)


def campus_snapshot(site):
    snapshot, identity = site.read(site.grid.build_snapshot)
    if snapshot is not None:
        snapshot.site = identity
        snapshot.contract = snapshot.contract.model_copy(update={"identity": snapshot.contract.identity.model_copy(update={"run_id": site.run_id, "state_revision": site.revision, "observation_time": snapshot.generated_at.isoformat()})})
    return snapshot


def socket_payload(snapshot, site):
    snapshot.site = site.identity()
    return WebSocketMessageEnvelope(type="snapshot", payload=snapshot,
        sent_at=datetime.now(timezone.utc)).model_dump_json()


async def run_replay(app, generation):
    grid, replay_data = app.state.grid, app.state.replay_data
    while grid.replay_running and generation == app.state.replay_generation:
        max_len = max((len(rows) for rows in replay_data.values()), default=0)
        if not max_len:
            grid.replay_running = False
            return
        index = grid.replay_index % max_len
        for cid, rows in replay_data.items():
            if not rows:
                continue
            row = rows[index % len(rows)]
            features = {key: row.get(key) for key in FEATURES}
            rev = grid.record_activity(cid, features, datetime.now(timezone.utc), "RECORDED_REPLAY", row.get("observed_at"))
            try:
                pred = await asyncio.to_thread(grid.model.predict, features)
            except Exception as exc:
                pred = {"state": "UNKNOWN", "score": None, "reason": f"inference failed: {type(exc).__name__}", "model_version": "unavailable"}
            if generation != app.state.replay_generation or not grid.replay_running:
                return
            grid.apply_prediction(cid, rev, pred)
        grid.replay_index = (index + 1) % max_len
        app.state.site.tick()
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_state(app)
    app.state.control_loop.start()
    try:
        yield
    finally:
        await app.state.control_loop.stop()
        if app.state.replay_task:
            app.state.replay_task.cancel()
            try:
                await app.state.replay_task
            except asyncio.CancelledError:
                pass
        for connection in list(app.state.manager.active_connections):
            await connection.close()
        app.state.manager.active_connections.clear()
        app.state.grid.storage.engine.dispose()


def get_grid_state(request: Request) -> GridState:
    return request.app.state.grid


router = APIRouter()
ELECTRICAL_TIMEOUT_S = 5


@router.get("/api/v1/health", response_model=HealthResponse)
async def health_check(request: Request):
    control_loop = request.app.state.control_loop
    return {
        "status": "ok",
        "application": "PriorityGrid",
        "control_loop": control_loop.health(),
    }

@router.get("/api/v1/snapshot", response_model=SystemSnapshot)
async def get_snapshot(request: Request):
    site = request.app.state.site
    snapshot = campus_snapshot(site)
    if snapshot is None:
        raise HTTPException(503, "control state not published yet")
    return snapshot

@router.get("/api/v1/model/status", response_model=ModelStatusResponse)
async def model_status(request: Request):
    grid = request.app.state.grid
    return grid.model.status()

@router.get("/api/v1/visualizers/classrooms")
async def get_classroom_demo(request: Request):
    site = request.app.state.site
    classroom_demo = request.app.state.classroom_demo
    return visualizer_snapshot(site, classroom_demo)

@router.post("/api/v1/visualizers/classrooms")
async def act_classroom_demo(request: Request, req: ClassroomDemoAction):
    site = request.app.state.site
    classroom_demo = request.app.state.classroom_demo
    if (req.action in ("scan", "unscan")) != (req.classroom_id is not None):
        raise HTTPException(422, "classroom_id is required only for scan and unscan")
    if (req.action == "set_capacity") != (req.capacity_w is not None):
        raise HTTPException(422, "capacity_w is required only for set_capacity")
    low, high = CLASSROOM_CAPACITY_RANGE_W
    if req.capacity_w is not None and not low <= req.capacity_w <= high:
        raise HTTPException(422, f"capacity_w must be between {low} and {high}")
    _, receipt = site.command(f"classroom.{req.action}",
                              lambda: classroom_demo.act(req.action, req.classroom_id, req.capacity_w))
    data, identity = site.read(classroom_demo.snapshot)
    return with_contract(data, site) | {"command": receipt}

@router.get("/api/v1/visualizers/hospital")
async def get_hospital_demo(request: Request):
    site = request.app.state.site
    hospital_demo = request.app.state.hospital_demo
    return visualizer_snapshot(site, hospital_demo)

@router.post("/api/v1/visualizers/hospital")
async def act_hospital_demo(request: Request, req: HospitalDemoAction):
    site = request.app.state.site
    hospital_demo = request.app.state.hospital_demo
    if req.scenario is not None:
        return with_contract(hospital_snapshot(req.scenario), site)
    if req.action is None:
        raise HTTPException(422, "either action or scenario must be provided")
    if req.capacity_w is not None:
        low, high = hospital_demo.snapshot()["capacity_range_w"]
        if not (low <= req.capacity_w <= high):
            raise HTTPException(422, f"capacity_w must be between {low} and {high}")
    _, receipt = site.command(f"hospital.{req.action}", lambda: hospital_demo.act(req.action, req.zone_id, req.capacity_w))
    data, identity = site.read(hospital_demo.snapshot)
    return with_contract(data, site) | {"command": receipt}

@router.post("/api/v1/activity/observations", response_model=ActivityObservationResponse)
async def post_activity_observation(request: Request, req: ActivityObservationRequest):
    grid = request.app.state.grid
    site = request.app.state.site
    if req.classroom_id not in ("CR1", "CR2", "CR3"):
        raise HTTPException(422, "classroom_id must be CR1, CR2, or CR3")
    if req.source not in ("RECORDED_REPLAY", "SIMULATED"):
        raise HTTPException(422, "source must be RECORDED_REPLAY or SIMULATED")
    try:
        observed_at = datetime.fromisoformat(req.observed_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(422, "observed_at must be an ISO timestamp")
    if observed_at.tzinfo is None:
        raise HTTPException(422, "observed_at must include a UTC offset")
    now = datetime.now(timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)
    if observed_at < now - timedelta(minutes=10) or observed_at > now + timedelta(seconds=30):
        raise HTTPException(422, "observed_at must be within the last 10 minutes and no more than 30 seconds ahead")
    bounds = {"temperature_c": (-10, 60), "humidity_pct": (0, 100), "co2_ppm": (250, 10000), "humidity_ratio": (0, 0.05)}
    features = {key: getattr(req, key) for key in FEATURES}
    for key, value in features.items():
        if value is not None and (isinstance(value, bool) or not math.isfinite(value) or not bounds[key][0] <= value <= bounds[key][1]):
            raise HTTPException(422, f"{key} is outside its accepted range")
    revision = grid.record_activity(req.classroom_id, features, observed_at, req.source)
    try:
        prediction = await asyncio.to_thread(grid.model.predict, features)
    except Exception as exc:
        prediction = {"state": "UNKNOWN", "score": None, "reason": f"inference failed: {type(exc).__name__}", "model_version": "unavailable"}
    applied = grid.apply_prediction(req.classroom_id, revision, prediction)
    site.commit("campus.activity_observation")
    return {"accepted": True, "applied": applied, "revision": revision,
            "activity": grid.activity[req.classroom_id]}

@router.post("/api/v1/replay", response_model=ReplayActionResponse)
async def replay_action(request: Request, req: ReplayActionRequest):
    grid = request.app.state.grid
    site = request.app.state.site
    replay_data = request.app.state.replay_data
    if req.action not in ("start", "pause", "reset"):
        raise HTTPException(422, "action must be start, pause, or reset")
    max_len = max((len(rows) for rows in replay_data.values()), default=0)
    if req.action == "start" and not max_len:
        raise HTTPException(409, "recorded replay data is unavailable")
    if req.action == "reset":
        request.app.state.replay_generation += 1
        if request.app.state.replay_task and not request.app.state.replay_task.done():
            request.app.state.replay_task.cancel()
        grid.replay_index = 0
        grid.replay_running = False
        for cid in ("CR1", "CR2", "CR3"):
            grid.set_classroom_load(cid, True)
            grid.activity_tokens[cid] += 1
            grid.activity_received_monotonic[cid] = None
            grid.activity_guard.reset(cid)
            grid.activity[cid] = {"state": "UNKNOWN", "score": None, "reason": "replay reset; awaiting evidence",
                                  "source": None, "observed_at": None, "recorded_at": None,
                                  "model_version": "unavailable", "priority": "UNKNOWN",
                                  "evidence": {key: None for key in FEATURES}}
    elif req.action == "pause":
        request.app.state.replay_generation += 1
        grid.replay_running = False
    elif not grid.replay_running:
        for cid in ("CR1", "CR2", "CR3"):
            grid.set_classroom_load(cid, True)
        grid.replay_running = True
        request.app.state.replay_generation += 1
        request.app.state.replay_task = asyncio.create_task(run_replay(request.app, request.app.state.replay_generation))
    grid.replay_length = max_len
    site.commit(f"campus.replay_{req.action}")
    return {"running": grid.replay_running, "index": grid.replay_index, "length": max_len}

@router.post("/api/v1/rfid/scan", response_model=RfidScanResponse)
async def process_rfid_scan(request: Request, req: RfidScanRequest):
    grid = request.app.state.grid
    site = request.app.state.site
    evt_type, class_id, class_name, service_id = grid.process_rfid_scan(req.uid)
    site.commit("campus.rfid_scan")
    return RfidScanResponse(
        accepted=True if evt_type != RfidEventType.DUPLICATE_SUPPRESSED.value else False,
        active_classroom_id=class_id,
        classroom_name=class_name,
        service_id=service_id,
        event_type=evt_type
    )

@router.post("/api/v1/simulation/capacity", response_model=CapacityChangeResponse)
async def change_capacity(request: Request, req: CapacityChangeRequest):
    grid = request.app.state.grid
    site = request.app.state.site
    grid.set_capacity(req.capacity_w)
    site.commit("campus.capacity")
    return CapacityChangeResponse(
        accepted=True,
        new_capacity_w=req.capacity_w,
        control_revision=grid.control_revision
    )

@router.post("/api/v1/simulation/classroom-load", response_model=ClassroomLoadResponse)
async def change_classroom_load(request: Request, req: ClassroomLoadRequest):
    grid = request.app.state.grid
    site = request.app.state.site
    if req.classroom_id not in ("CR1", "CR2", "CR3"):
        raise HTTPException(422, "classroom_id must be CR1, CR2, or CR3")
    grid.set_classroom_load(req.classroom_id, req.active)
    site.commit("campus.classroom_load")
    return ClassroomLoadResponse(
        accepted=True,
        classroom_id=req.classroom_id,
        load_event_active=req.active
    )

@router.post("/api/v1/simulation/feeder", response_model=FeederChangeResponse)
async def change_feeder(request: Request, req: FeederChangeRequest):
    grid = request.app.state.grid
    site = request.app.state.site
    if req.feeder not in ("A", "B"):
        raise HTTPException(422, "feeder must be A or B")
    grid.set_feeder(req.feeder, req.available)
    site.commit("campus.feeder")
    return FeederChangeResponse(
        accepted=True,
        feeder=req.feeder,
        available=req.available,
        control_revision=grid.control_revision
    )

@router.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    site = websocket.app.state.site
    manager = websocket.app.state.manager
    await manager.connect(websocket)
    snapshot = campus_snapshot(site)
    if snapshot is not None:
        await websocket.send_text(socket_payload(snapshot, site))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.get("/api/v1/allocation/policy")
async def read_allocation_policy(request: Request):
    grid = request.app.state.grid
    site = request.app.state.site
    return site.read(lambda: grid.policy.model_dump())[0]

@router.put("/api/v1/allocation/policy")
async def change_allocation_policy(request: Request, policy: AllocationPolicy):
    grid = request.app.state.grid
    site = request.app.state.site
    def apply():
        with grid._lock:
            grid.policy = policy
            grid.control_revision += 1
            grid.add_event("POLICY_CHANGE", policy.model_dump_json())
    _, receipt = site.command("allocation_policy", apply)
    return {"policy": policy.model_dump(), "receipt": receipt}

@router.post("/api/v1/studies/electrical", response_model=ElectricalStudyResponse)
async def electrical_study(request: Request, inputs: ElectricalInput):
    site = request.app.state.site
    electrical_study_lock = request.app.state.electrical_study_lock
    if electrical_study_lock.locked():
        raise HTTPException(503, "Electrical study busy; retry later")
    await electrical_study_lock.acquire()
    identity = site.identity()
    async def work():
        try:
            return await asyncio.to_thread(solve_electrical, inputs)
        finally:
            electrical_study_lock.release()
    task = asyncio.create_task(work())
    try:
        result = await asyncio.wait_for(asyncio.shield(task), timeout=ELECTRICAL_TIMEOUT_S)
    except TimeoutError:
        raise HTTPException(504, "Electrical study timed out; no control or restoration applied")
    if site.identity() != identity:
        raise HTTPException(409, "Site run/revision changed during study; discard and retry")
    return {"site": identity, "result": result.model_dump(), "diagnosis": diagnose_study(result)}

def with_contract(data, site):
    data = with_site(data, site.identity())
    data["contract"] = {"identity": {**site.grid.identity(), "run_id": site.run_id,
        "state_revision": site.revision}, "zone_totals": {}}
    return data


def visualizer_snapshot(site, demo):
    with site._lock:
        return with_contract(demo.snapshot(), site)


@router.post("/api/v1/hardware/ack", response_model=HardwareAckResponse)
async def hardware_ack(request: Request, req: HardwareAckRequest):
    try:
        request.app.state.site.command("hardware_ack", lambda: request.app.state.grid.record_ack(
            req.device_boot, req.sequence, req.session, req.confirmed_mask, req.provenance))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"accepted": True}


def create_app():
    application = FastAPI(title="PriorityGrid API", version="1.0.0", lifespan=lifespan)
    application.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    application.include_router(router)
    return application


app = create_app()
