from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from typing import Dict

from app.schemas.snapshot import (
    SystemSnapshot,
    ServiceSnapshot,
    SourceInfo,
    SourceKind,
    HardwareLinkStatus,
    Tier
)

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

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok",
        "application": "PriorityGrid"
    }

@app.get("/api/v1/snapshot", response_model=SystemSnapshot)
async def get_snapshot():
    # Constructing the 6 services exactly as specified
    services = [
        ServiceSnapshot(
            id="L0",
            name="Clinic Essential Circuit",
            tier=Tier.T1,
            feeder="A",
            watts=2000,
            requested=True,
            modeled_served=True,
            indicator_confirmed=None,
            model_reason="Initial nominal demonstration state."
        ),
        ServiceSnapshot(
            id="L1",
            name="Emergency Lighting",
            tier=Tier.T1,
            feeder="A",
            watts=1000,
            requested=True,
            modeled_served=True,
            indicator_confirmed=None,
            model_reason="Initial nominal demonstration state."
        ),
        ServiceSnapshot(
            id="L2",
            name="Water Pump",
            tier=Tier.T2,
            feeder="A",
            watts=3000,
            requested=True,
            modeled_served=True,
            indicator_confirmed=None,
            model_reason="Initial nominal demonstration state."
        ),
        ServiceSnapshot(
            id="L3",
            name="Communications Room",
            tier=Tier.T2,
            feeder="B",
            watts=2000,
            requested=True,
            modeled_served=True,
            indicator_confirmed=None,
            model_reason="Initial nominal demonstration state."
        ),
        ServiceSnapshot(
            id="L4",
            name="Cold Storage",
            tier=Tier.T2,
            feeder="B",
            watts=2000,
            requested=True,
            modeled_served=True,
            indicator_confirmed=None,
            model_reason="Initial nominal demonstration state."
        ),
        ServiceSnapshot(
            id="L5",
            name="Comfort Cooling",
            tier=Tier.T3,
            feeder="B",
            watts=4000,
            requested=True,
            modeled_served=True,
            indicator_confirmed=None,
            model_reason="Initial nominal demonstration state."
        ),
    ]

    return SystemSnapshot(
        control_revision=0,
        generated_at=datetime.now(timezone.utc),
        source=SourceInfo(
            kind=SourceKind.SIMULATED,
            capacity_w=14000
        ),
        feeder_limits_w={
            "A": 6000,
            "B": 8000
        },
        requested_mask=63,
        modeled_mask=63,
        indicator_mask=None,
        hardware_link=HardwareLinkStatus.NOT_CONNECTED,
        services=services
    )
