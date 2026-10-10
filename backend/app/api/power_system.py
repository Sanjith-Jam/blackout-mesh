"""Appliance-level projection of the one site decision, and per-appliance request commands.

Read-only projection under the site lock: nothing here advances control or recomputes allocation.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.core import appliances as cat
from app.core.active_site import CATALOG
from app.core.appliance_control import PENDING, SERVED, UNREACHABLE
from app.schemas.power_system import ApplianceRequest, ApplianceRequestResponse, PowerSystemResponse

BOUNDARY = ("Simulated power system. Watts are configured demonstration values, not measurements. Served means "
            "served in the model; it does not prove electricity reached a device. Only a board B acknowledgment "
            "confirms an indicator LED, and an LED does not prove appliance power.")

DIAGNOSIS_STATUS = {"NORMAL": "NORMAL", "FAULT_DETECTED": "FAULT_DETECTED", "ALARM": "SUSPECTED",
                    "ABSTAINED": "INCONCLUSIVE"}


def _edge_state(available: bool, requested_w: int, commanded_w: int, served_w: int) -> str:
    if not available:
        return "OPEN"
    if served_w > 0:
        return "ENERGIZED"
    if commanded_w > 0:
        return "PENDING_RESTORATION"
    return "SHED"


def _constraint(cid, scope, label, requested, limit, served, provenance="DERIVED"):
    return {"id": cid, "scope": scope, "label": label, "requested_w": requested, "limit_w": limit, "served_w": served,
            "exceeded": requested > limit, "deficit_w": max(0, requested - limit), "headroom_w": max(0, limit - served),
            "provenance": provenance}


def build_power_system(site, hardware: dict) -> dict:
    grid, ctrl, hospital, classroom = site.grid, site.appliances, site.hospital, site.classroom
    problem, plan = ctrl.problem, ctrl.plan
    items = {it.id: it for it in problem.items}
    rank = {c: i for i, c in enumerate(problem.class_order)}
    recent = {}
    for ev in ctrl.events:
        recent.setdefault(ev["appliance_id"], []).append(ev)

    def ev_out(ev):
        return {"timestamp": ev["timestamp"], "appliance_id": ev["appliance_id"], "to": ev["to"],
                "from_state": ev["from"], "reason": ev["reason"], "command": ev["command"], "provenance": ev["provenance"]}

    appliances = []
    for a in cat.APPLIANCES:
        it = items[a.id]
        state = ctrl.state_of(it)
        reason = ctrl.reasons[a.id]
        appliances.append({
            "id": a.id, "asset_id": a.asset_id, "key": a.key, "name": a.name, "room_id": a.room_id, "zone": a.zone,
            "feeder": a.feeder, "service_id": a.service_id, "distribution_id": a.distribution_id, "demand_w": a.demand_w,
            "service_tier": a.service_tier, "essential": a.essential, "protected": it.cls in cat.PROTECTED_CLASSES,
            "priority_class": it.cls, "priority_label": cat.CLASS_LABELS[it.cls], "priority_rank": rank[it.cls] + 1,
            "requested": it.requested, "reachable": it.reachable, "commanded": a.id in plan.served,
            "served": state == SERVED, "served_w": a.demand_w if state == SERVED else 0, "state": state,
            "reason_code": reason["code"], "reason": reason["text"], "path": cat.path(a), "requires": list(a.requires),
            "indivisible_group": a.indivisible_group, "provenance": "CONFIGURED_SIMULATED_ASSUMPTION",
            "events": [ev_out(e) for e in recent.get(a.id, [])[-5:]]})

    def total(pred, field):
        return sum(x["demand_w"] for x in appliances if pred(x) and x[field])

    req = lambda pred: total(pred, "requested")
    com = lambda pred: sum(x["demand_w"] for x in appliances if pred(x) and x["commanded"] and x["reachable"])
    srv = lambda pred: total(pred, "served")

    feeders = []
    for f in sorted(CATALOG.feeder_limits_w):
        on_f = lambda x, f=f: x["feeder"] == f
        feeders.append({"id": f, "name": f"Feeder {f}", "available": bool(grid.feeder_available.get(f, False)),
                        "limit_w": grid.feeder_limits_w[f], "requested_w": req(on_f), "commanded_w": com(on_f),
                        "served_w": srv(on_f)})
    everything = lambda x: True
    source = {"id": cat.SOURCE_ID, "name": cat.SOURCE_NAME, "capacity_w": grid.source_capacity_w,
              "normal_capacity_w": CATALOG.source_capacity_w, "requested_w": req(everything),
              "commanded_w": com(everything), "served_w": srv(everything), "provenance": "SIMULATED"}
    zone_budgets = [
        {"zone": "hospital", "limit_w": hospital.capacity, "normal_limit_w": hospital.NORMAL_W,
         "requested_w": req(lambda x: x["zone"] == "hospital"), "served_w": srv(lambda x: x["zone"] == "hospital")},
        {"zone": "classroom", "limit_w": classroom.capacity, "normal_limit_w": CATALOG.feeder_limits_w["B"],
         "requested_w": req(lambda x: x["zone"] == "classroom"), "served_w": srv(lambda x: x["zone"] == "classroom")}]

    transformers = {t["zone"]: t for t in (hospital.published or {}).get("transformers", [])}
    sessions = set(classroom.scanned)
    rooms = []
    for r in cat.ROOMS:
        in_r = lambda x, r=r: x["room_id"] == r["id"]
        if r["zone"] == "hospital":
            diag = (transformers.get(r["id"]) or {}).get("diagnosis") or {}
            status = DIAGNOSIS_STATUS.get(diag.get("status"), "UNKNOWN")
            abstention = diag.get("abstention") if isinstance(diag.get("abstention"), dict) else {}
            detail = diag.get("cause") or abstention.get("reason") or abstention.get("summary")
            session, activity = None, None
        else:
            status, detail = "NOT_INSTRUMENTED", "No per-room electrical sensors are configured for classrooms."
            session = r["id"] in sessions
            activity = classroom.activity(r["id"]).get("state")
        rooms.append({**{k: r[k] for k in ("id", "name", "zone", "feeder", "distribution_id", "distribution_name", "service_id")},
                      "requested_w": req(in_r), "commanded_w": com(in_r), "served_w": srv(in_r), "session": session,
                      "activity_state": activity, "evidence_status": status, "evidence_detail": detail})

    # Edges: one per configured connection, state from the applied decision below it.
    feeder_by_id = {f["id"]: f for f in feeders}
    by_app = {x["id"]: x for x in appliances}
    edges = []
    for e in cat.edges():
        downstream = [x for x in appliances if e["to"] in x["path"]]
        if e["kind"] == "branch":
            x = by_app[e["to"]]
            state = ("OPEN" if not x["reachable"] else "ENERGIZED" if x["state"] == SERVED else
                     "PENDING_RESTORATION" if x["state"] == PENDING else "SHED")
        else:
            available = grid.source_capacity_w > 0 and all(
                feeder_by_id[n]["available"] for n in feeder_by_id if n in (e["from"], e["to"]))
            if e["kind"] == "distribution" and any(x["zone"] == "hospital" for x in downstream):
                available = available and all(x["reachable"] or not x["requested"] for x in downstream)
            state = _edge_state(available, sum(x["demand_w"] for x in downstream if x["requested"]),
                                sum(x["demand_w"] for x in downstream if x["commanded"] and x["reachable"]),
                                sum(x["served_w"] for x in downstream))
        edges.append({"id": e["id"], "from_node": e["from"], "to_node": e["to"], "kind": e["kind"], "state": state,
                      "requested_w": sum(x["demand_w"] for x in downstream if x["requested"]),
                      "served_w": sum(x["served_w"] for x in downstream)})

    checks = [_constraint("source", "source", f"{cat.SOURCE_NAME} capacity", source["requested_w"], source["capacity_w"],
                          source["served_w"])]
    for f in feeders:
        checks.append(_constraint(f"feeder:{f['id']}", "feeder", f"Feeder {f['id']} limit", f["requested_w"],
                                  f["limit_w"] if f["available"] else 0, f["served_w"]))
    for z in zone_budgets:
        checks.append(_constraint(f"zone:{z['zone']}", "zone", f"{z['zone'].title()} budget", z["requested_w"],
                                  z["limit_w"], z["served_w"]))

    faults = []
    for f in feeders:
        if not f["available"]:
            faults.append({"id": f"feeder:{f['id']}", "kind": "FEEDER_OPEN", "target": f["id"],
                           "description": f"Feeder {f['id']} switched open in the simulation.", "provenance": "INJECTED_SIMULATION"})
    if grid.source_capacity_w < CATALOG.source_capacity_w:
        faults.append({"id": "source:capacity", "kind": "CAPACITY_REDUCED", "target": cat.SOURCE_ID,
                       "description": f"Source capacity set to {grid.source_capacity_w:,} W of {CATALOG.source_capacity_w:,} W.",
                       "provenance": "INJECTED_SIMULATION"})
    for z in zone_budgets:
        if z["limit_w"] < z["normal_limit_w"]:
            faults.append({"id": f"zone:{z['zone']}", "kind": "ZONE_BUDGET_REDUCED", "target": z["zone"],
                           "description": f"{z['zone'].title()} budget set to {z['limit_w']:,} W of {z['normal_limit_w']:,} W.",
                           "provenance": "INJECTED_SIMULATION"})
    if hospital.fault:
        faults.append({"id": f"hospital:{hospital.fault['kind']}", "kind": hospital.fault["kind"].upper(),
                       "target": hospital.fault["zone"], "description": f"Injected {hospital.fault['kind'].replace('_', ' ')} at {hospital.fault['zone']}.",
                       "provenance": "INJECTED_SIMULATION"})

    raw = grid.campus_diagnosis
    if raw is None:
        campus = {"status": "UNKNOWN", "detail": "No diagnosis has been evaluated yet.", "hypotheses": [],
                  "affected_assets": [], "evaluated_at": None}
    else:
        campus = {"status": DIAGNOSIS_STATUS.get(raw["status"], "UNKNOWN"), "detail": raw["diagnosis"],
                  "hypotheses": raw["hypotheses"], "affected_assets": raw["affected_assets"],
                  "evaluated_at": raw.get("evaluated_at"), "raw_status": raw["status"]}
    campus["provenance"] = "SIMULATED_TELEMETRY"
    campus["inputs"] = "Bus and feeder voltage envelopes only; configured capacity is not fault evidence."
    statuses = [campus["status"], *(r["evidence_status"] for r in rooms if r["zone"] == "hospital")]
    exceeded = any(c["exceeded"] for c in checks)
    overall = ("FAULT_DETECTED" if "FAULT_DETECTED" in statuses else "SUSPECTED" if "SUSPECTED" in statuses else
               "INCONCLUSIVE" if ("INCONCLUSIVE" in statuses or "UNKNOWN" in statuses) else
               "CONSTRAINT_ACTIVE" if exceeded else "NORMAL")
    diagnosis = {"overall": overall, "campus": campus,
                 "transformers": [{"zone": z, "asset_id": t.get("id"), "status": DIAGNOSIS_STATUS.get((t.get("diagnosis") or {}).get("status"), "UNKNOWN"),
                                   "diagnosis": t.get("diagnosis"), "sensors": t.get("sensors"),
                                   "provenance": "SIMULATED_TELEMETRY"} for z, t in transformers.items()],
                 "constraint_violation": exceeded,
                 "note": "Diagnosis reads simulated telemetry only. Constraint checks compare configured demand with configured limits."}

    indicator_cmd = (grid.published.indicator_command_mask if grid.published else 0) or 0
    confirmed = hardware.get("confirmed_mask")
    link = hardware.get("link", "NOT_CONFIGURED")
    indicators = []
    for room in CATALOG.hospital_rooms:
        indicators.append({"led_bit": room["led_bit"], "room_id": room["id"], "name": room["name"],
                           "rule": f"Virtual indicator: on when some of service {room['lighting_service']} is served. No physical LED is wired.",
                           "commanded": bool(indicator_cmd >> room["led_bit"] & 1), "confirmed": None})
    physical = desired_led_mask_from(site)
    for c in CATALOG.classrooms:
        indicators.append({"led_bit": c["led_bit"], "room_id": c["id"], "name": c["name"],
                           "rule": "Board B LED: on when the room has a session and every one of its appliances is served.",
                           "commanded": bool(physical >> c["led_bit"] & 1),
                           "confirmed": None if confirmed is None or link != "CONNECTED" else bool(confirmed >> c["led_bit"] & 1)})

    events = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in grid.events[-30:]]
    return {"site": site.identity(), "generated_at": datetime.now(timezone.utc).isoformat(), "boundary": BOUNDARY,
            "source": source, "feeders": feeders, "zone_budgets": zone_budgets, "rooms": rooms,
            "appliances": appliances, "edges": edges, "optimizer": {**ctrl.summary(), "baseline": {
                "description": "Six-service allocator kept as a regression fixture; it no longer decides appliances.",
                "campus_service_proposed_mask": grid.proposed_mask, "campus_service_applied_mask": grid.last_allocation_mask}},
            "diagnosis": diagnosis, "constraint_checks": checks, "faults": faults, "indicators": indicators,
            "hardware_link": link, "events": events,
            "appliance_events": [ev_out(e) for e in list(ctrl.events)[-40:]]}


def desired_led_mask_from(site) -> int:
    from app.main import led_mask  # local import: app.main imports this module
    return led_mask(site.classroom.published or {})


def register_power_system(hardware_status):
    router = APIRouter()

    @router.get("/api/v1/power-system", response_model=PowerSystemResponse)
    async def get_power_system(request: Request):
        site = request.app.state.site
        hardware = hardware_status(request.app)
        return site.read(lambda: build_power_system(site, hardware))[0]

    @router.post("/api/v1/appliances/request", response_model=ApplianceRequestResponse)
    async def request_appliance(request: Request, req: ApplianceRequest):
        site = request.app.state.site
        if req.appliance_id not in cat.APPLIANCE_BY_ID:
            raise HTTPException(422, f"unknown appliance {req.appliance_id!r}")
        def apply():
            site.appliances.set_requested(req.appliance_id, req.requested)
            site.grid.add_event("APPLIANCE_REQUEST", f"{req.appliance_id} requested {'on' if req.requested else 'off'}")

        site.command("appliance.request", apply, {"appliance_id": req.appliance_id, "requested": req.requested})
        return {"accepted": True, "appliance_id": req.appliance_id, "requested": req.requested, "site": site.identity()}

    return router
