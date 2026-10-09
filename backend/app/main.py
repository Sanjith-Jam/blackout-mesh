import asyncio
import json
import math
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Literal
from pydantic import BaseModel, ConfigDict

from app.schemas.snapshot import (
    HealthResponse, ModelStatusResponse, ClassroomDemoSnapshot, HospitalDemoSnapshot,
    ActivityObservationResponse, ReplayActionResponse, WebSocketMessageEnvelope, HardwareAckRequest, HardwareAckResponse,
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
from app.activity.model import FEATURES
from app.visualizers import ClassroomDemo, hospital_snapshot

class ClassroomDemoAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["scan", "unscan", "normal", "overload", "reset"]
    classroom_id: Literal["CR1", "CR2", "CR3"] | None = None

class HospitalDemoAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["normal", "overload", "cooling_failure", "upstream_loss", "missing_sensor"]

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


async def broadcast_state(app: FastAPI):
    while True:
        if app.state.manager.active_connections:
            try:
                snapshot = app.state.grid.build_snapshot()
                envelope = WebSocketMessageEnvelope(type="snapshot", payload=snapshot)
                await app.state.manager.broadcast(envelope.model_dump_json())
            except Exception as e:
                print(f"Broadcast error: {e}")
        await asyncio.sleep(0.25)

async def run_replay(app: FastAPI, generation: int):
    while app.state.grid.replay_running and generation == app.state.replay_generation:
        max_len = max((len(rows) for rows in app.state.replay_data.values()), default=0)
        if not max_len:
            app.state.grid.replay_running = False
            return
        index = app.state.grid.replay_index % max_len
        for cid in ("CR1", "CR2", "CR3"):
            rows = app.state.replay_data.get(cid, [])
            if not rows:
                continue
            row = rows[index % len(rows)]
            features = {key: row.get(key) for key in FEATURES}
            observed_at = datetime.now(timezone.utc)
            rev = app.state.grid.record_activity(cid, features, observed_at, "RECORDED_REPLAY", row.get("observed_at"))
            try:
                pred = await asyncio.to_thread(app.state.grid.model.predict, features)
            except Exception as exc:
                pred = {"state": "UNKNOWN", "score": None, "reason": f"inference failed: {type(exc).__name__}", "model_version": "unavailable"}
            if generation != app.state.replay_generation or not app.state.grid.replay_running:
                return
            app.state.grid.apply_prediction(cid, rev, pred)
        app.state.grid.replay_index = (index + 1) % max_len
        await asyncio.sleep(1)



REPLAY_PATH = Path(__file__).resolve().parents[1] / "models" / "replay.json"

def load_replay():
    try:
        data = json.loads(REPLAY_PATH.read_text())
        return {cid: rows for cid, rows in data.items() if cid in ("CR1", "CR2", "CR3") and isinstance(rows, list)}
    except (OSError, ValueError):
        return {}

@asynccontextmanager

async def lifespan(app: FastAPI):
    app.state.manager = ConnectionManager()
    app.state.replay_data = load_replay()
    app.state.grid = GridState()
    app.state.grid.replay_length = max((len(rows) for rows in app.state.replay_data.values()), default=0)
    app.state.classroom_demo = ClassroomDemo()
    app.state.hospital_scenario = "normal"
    app.state.replay_generation = 0
    app.state.broadcast_task = asyncio.create_task(broadcast_state(app))
    app.state.replay_task = None
    
    yield
    
    if app.state.broadcast_task:
        app.state.broadcast_task.cancel()
        try:
            await app.state.broadcast_task
        except asyncio.CancelledError:
            pass
            
    if app.state.replay_task:
        app.state.replay_task.cancel()
        try:
            await app.state.replay_task
        except asyncio.CancelledError:
            pass
            
    for conn in list(app.state.manager.active_connections):
        try:
            await conn.close()
        except Exception:
            pass
    app.state.manager.active_connections.clear()


def get_grid_state(request: Request) -> GridState:
    return request.app.state.grid

def get_manager(request: Request) -> ConnectionManager:
    return request.app.state.manager

def get_classroom_demo_instance(request: Request) -> ClassroomDemo:
    return request.app.state.classroom_demo

app = FastAPI(
    title="PriorityGrid API",
    description="Backend API for the PriorityGrid decision-and-control application.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "ok",
        "application": "PriorityGrid"
    }

@app.get("/api/v1/snapshot", response_model=SystemSnapshot)
async def get_snapshot(grid: GridState = Depends(get_grid_state)):
    return grid.build_snapshot()

@app.get("/api/v1/model/status", response_model=ModelStatusResponse)
async def model_status(grid: GridState = Depends(get_grid_state)):
    return grid.model.status()

@app.get("/api/v1/visualizers/classrooms", response_model=ClassroomDemoSnapshot)
async def get_classroom_demo_api(classroom_demo: ClassroomDemo = Depends(get_classroom_demo_instance)):
    return classroom_demo.snapshot()

@app.post("/api/v1/visualizers/classrooms", response_model=ClassroomDemoSnapshot)
async def act_classroom_demo(req: ClassroomDemoAction, classroom_demo: ClassroomDemo = Depends(get_classroom_demo_instance)):
    if (req.action in ("scan", "unscan")) != (req.classroom_id is not None):
        raise HTTPException(422, "classroom_id is required only for scan or unscan")
    return classroom_demo.act(req.action, req.classroom_id)

@app.get("/api/v1/visualizers/hospital", response_model=HospitalDemoSnapshot)
async def get_hospital_demo(request: Request):
    return hospital_snapshot(request.app.state.hospital_scenario)

@app.post("/api/v1/visualizers/hospital", response_model=HospitalDemoSnapshot)
async def act_hospital_demo(req: HospitalDemoAction, request: Request):
    request.app.state.hospital_scenario = req.scenario
    return hospital_snapshot(request.app.state.hospital_scenario)

@app.post("/api/v1/activity/observations", response_model=ActivityObservationResponse)
async def post_activity_observation(req: ActivityObservationRequest, grid: GridState = Depends(get_grid_state)):
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
    return {"accepted": True, "applied": applied, "revision": revision,
            "activity": grid.activity[req.classroom_id]}

@app.post("/api/v1/replay", response_model=ReplayActionResponse)
async def replay_action(req: ReplayActionRequest, request: Request, grid: GridState = Depends(get_grid_state)):
    if req.action not in ("start", "pause", "reset"):
        raise HTTPException(422, "action must be start, pause, or reset")
    max_len = max((len(rows) for rows in request.app.state.replay_data.values()), default=0)
    if req.action == "start" and not max_len:
        raise HTTPException(409, "recorded replay data is unavailable")
    if req.action == "reset":
        request.app.state.replay_generation += 1
        if request.app.state.replay_task and not request.app.state.replay_task.done():
            request.app.state.replay_task.cancel()
        grid.replay_index = 0
        app.state.grid.replay_running = False
        for cid in ("CR1", "CR2", "CR3"):
            app.state.grid.set_classroom_load(cid, True)
            grid.activity_tokens[cid] += 1
            grid.activity_received_monotonic[cid] = None
            grid.activity[cid] = {"state": "UNKNOWN", "score": None, "reason": "replay reset; awaiting evidence",
                                  "source": None, "observed_at": None, "recorded_at": None,
                                  "model_version": "unavailable", "priority": "UNKNOWN",
                                  "evidence": {key: None for key in FEATURES}}
    elif req.action == "pause":
        request.app.state.replay_generation += 1
        app.state.grid.replay_running = False
    elif not app.state.grid.replay_running:
        for cid in ("CR1", "CR2", "CR3"):
            app.state.grid.set_classroom_load(cid, True)
        grid.replay_running = True
        request.app.state.replay_generation += 1
        request.app.state.replay_task = asyncio.create_task(run_replay(request.app, request.app.state.replay_generation))
    grid.replay_length = max_len
    return {"running": grid.replay_running, "index": grid.replay_index, "length": max_len}

@app.post("/api/v1/rfid/scan", response_model=RfidScanResponse)
async def process_rfid_scan(req: RfidScanRequest, grid: GridState = Depends(get_grid_state)):
    evt_type, class_id, class_name, service_id = grid.process_rfid_scan(req.uid)
    return RfidScanResponse(
        accepted=True if evt_type != RfidEventType.DUPLICATE_SUPPRESSED.value else False,
        active_classroom_id=class_id,
        classroom_name=class_name,
        service_id=service_id,
        event_type=evt_type
    )

@app.post("/api/v1/simulation/capacity", response_model=CapacityChangeResponse)
async def change_capacity(req: CapacityChangeRequest, grid: GridState = Depends(get_grid_state)):
    grid.set_capacity(req.capacity_w)
    return CapacityChangeResponse(
        accepted=True,
        new_capacity_w=req.capacity_w,
        control_revision=grid.control_revision
    )

@app.post("/api/v1/simulation/classroom-load", response_model=ClassroomLoadResponse)
async def change_classroom_load(req: ClassroomLoadRequest, grid: GridState = Depends(get_grid_state)):
    if req.classroom_id not in ("CR1", "CR2", "CR3"):
        raise HTTPException(422, "classroom_id must be CR1, CR2, or CR3")
    app.state.grid.set_classroom_load(req.classroom_id, req.active)
    return ClassroomLoadResponse(
        accepted=True,
        classroom_id=req.classroom_id,
        load_event_active=req.active
    )

@app.post("/api/v1/simulation/feeder", response_model=FeederChangeResponse)
async def change_feeder(req: FeederChangeRequest, grid: GridState = Depends(get_grid_state)):
    if req.feeder not in ("A", "B"):
        raise HTTPException(422, "feeder must be A or B")
    grid.set_feeder(req.feeder, req.available)
    return FeederChangeResponse(
        accepted=True,
        feeder=req.feeder,
        available=req.available,
        control_revision=grid.control_revision
    )


@app.post("/api/v1/hardware/ack", response_model=HardwareAckResponse)
async def hardware_ack(req: HardwareAckRequest, grid: GridState = Depends(get_grid_state)):
    grid.record_ack(req.device_boot, req.sequence, req.session, req.confirmed_mask, req.provenance)
    return HardwareAckResponse(accepted=True)

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket, manager: ConnectionManager = Depends(get_manager)):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
