from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from typing import Dict

from app.schemas.snapshot import (
    SystemSnapshot,
    RfidScanRequest,
    RfidScanResponse,
    RfidEventType,
    CapacityChangeRequest,
    CapacityChangeResponse,
    ClassroomLoadRequest,
    ClassroomLoadResponse,
    FeederChangeRequest,
    FeederChangeResponse
)
from app.core.state import GridState

app = FastAPI(
    title="PriorityGrid API",
    description="Backend API for the PriorityGrid decision-and-control application.",
    version="1.0.0"
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

grid = GridState()

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok",
        "application": "PriorityGrid"
    }

@app.get("/api/v1/snapshot", response_model=SystemSnapshot)
async def get_snapshot():
    return grid.build_snapshot()

@app.post("/api/v1/rfid/scan", response_model=RfidScanResponse)
async def process_rfid_scan(req: RfidScanRequest):
    evt_type, class_id, class_name, service_id = grid.process_rfid_scan(req.uid)
    return RfidScanResponse(
        accepted=True if evt_type != RfidEventType.DUPLICATE_SUPPRESSED.value else False,
        active_classroom_id=class_id,
        classroom_name=class_name,
        service_id=service_id,
        event_type=evt_type
    )

@app.post("/api/v1/simulation/capacity", response_model=CapacityChangeResponse)
async def change_capacity(req: CapacityChangeRequest):
    grid.set_capacity(req.capacity_w)
    return CapacityChangeResponse(
        accepted=True,
        new_capacity_w=req.capacity_w,
        control_revision=grid.control_revision
    )

@app.post("/api/v1/simulation/classroom-load", response_model=ClassroomLoadResponse)
async def change_classroom_load(req: ClassroomLoadRequest):
    grid.set_classroom_load(req.classroom_id, req.active)
    return ClassroomLoadResponse(
        accepted=True,
        classroom_id=req.classroom_id,
        load_event_active=req.active
    )

@app.post("/api/v1/simulation/feeder", response_model=FeederChangeResponse)
async def change_feeder(req: FeederChangeRequest):
    grid.set_feeder(req.feeder, req.available)
    return FeederChangeResponse(
        accepted=True,
        feeder=req.feeder,
        available=req.available,
        control_revision=grid.control_revision
    )
