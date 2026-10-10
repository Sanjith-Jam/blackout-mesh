"""One revision for the city story, plus measured software evidence."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.schemas.snapshot import HardwareStatusResponse, SystemSnapshot

ROOT = Path(__file__).resolve().parents[2]


class ForecastPoint(BaseModel):
    ahead_s: int
    demand_w: int
    lower_w: int
    upper_w: int


class DemandForecastResponse(BaseModel):
    source: Literal["LIVE_REQUESTED_DEMAND", "SYNTHETIC_REPLAY"]
    model_version: str
    sample_s: int
    sample_age_s: float | None
    observations_w: list[int]
    points: list[ForecastPoint]
    status: Literal["UNKNOWN", "SHORTAGE_RISK", "WITHIN_CAPACITY"]
    reason: str
    first_shortage_s: int | None
    capacity_w: int


class AblationRow(BaseModel):
    policy: str
    occupied_service_pct: float
    switching_count: float
    essential_unmet_wh: float
    critical_unmet_wh: float


class DemoEvidence(BaseModel):
    inference_median_ms: float | None = None
    inference_calls: int | None = None
    allocation_median_ms: float | None = None
    allocation_calls: int | None = None
    masks: int | None = None
    allocation_runs: int | None = None
    constraint_violations: int | None = None
    forecast_mae_60s_w: float | None = None
    persistence_mae_60s_w: float | None = None
    forecast_test_sessions: int | None = None
    ablation: list[AblationRow] = []


@lru_cache
def evidence():
    def read(path):
        try:
            return json.loads((ROOT / path).read_text())
        except (OSError, ValueError):
            return {}
    inference = read("models/evaluation.json").get("runtime_inference", {}).get("warm_single_prediction_ms", {})
    profile = read("benchmarks/results/allocation_profile.json").get("services6", {})
    allocation = read("benchmarks/results/allocation_report.json")
    forecast = read("models/DEMAND_FORECAST_REPORT.json")
    return DemoEvidence(inference_median_ms=inference.get("median_ms"), inference_calls=inference.get("n"),
                        allocation_median_ms=profile.get("median_ms"), allocation_calls=profile.get("n"), masks=profile.get("masks"),
                        allocation_runs=len(allocation["runs"]) if "runs" in allocation else None,
                        constraint_violations=sum(r["constraint_violations"] for r in allocation["runs"]) if "runs" in allocation else None,
                        forecast_mae_60s_w=forecast.get("mae_w", [None])[-1],
                        persistence_mae_60s_w=forecast.get("persistence_mae_w", [None])[-1],
                        forecast_test_sessions=forecast.get("sessions", {}).get("test"),
                        ablation=[AblationRow(policy=key.split("|", 1)[1], occupied_service_pct=100 * row["occupied_service_fraction"],
                                             switching_count=row["switching_count"], essential_unmet_wh=row["essential_unmet_wh"],
                                             critical_unmet_wh=row["critical_unmet_wh"])
                                  for key, row in allocation.get("summary", {}).items() if key.startswith("shortage_6kw|")])


class CityDemoResponse(BaseModel):
    snapshot: SystemSnapshot
    forecast: DemandForecastResponse
    hardware: HardwareStatusResponse


def register_demo(campus_snapshot, hardware_status):
    router = APIRouter()

    @router.get("/api/v1/demo/evidence", response_model=DemoEvidence)
    async def get_evidence():
        return evidence()

    @router.get("/api/v1/demo", response_model=CityDemoResponse)
    async def get_city_demo(request: Request, source: Literal["LIVE_REQUESTED_DEMAND", "SYNTHETIC_REPLAY"] = "LIVE_REQUESTED_DEMAND",
                            replay_index: int = Query(default=3, ge=0, le=7)):
        app = request.app
        site = app.state.site
        def project():
            snap = campus_snapshot(site)
            forecast = app.state.demand_forecast.predict(snap.source.capacity_w, source, replay_index)
            if source == "LIVE_REQUESTED_DEMAND" and app.state.demand_forecast.run_id != site.run_id:
                forecast.update(status="UNKNOWN", points=[], observations_w=[], first_shortage_s=None,
                                reason="A new run is collecting fresh demand observations.")
            return dict(snapshot=snap, forecast=forecast)
        data = site.read(project)[0]
        # Gateway events acquire the site lock; never take the gateway lock while holding it.
        data["hardware"] = hardware_status(app)
        return data

    return router
