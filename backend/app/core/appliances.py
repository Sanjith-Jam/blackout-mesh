"""Site-wide appliance catalog: every configured leaf load with an explicit identity.

Built only from the validated site profile; nothing here adds equipment or changes a rating. Every
watt value is a configured demonstration assumption (the profile is a simulated site), not a
measured or manufacturer rating. Rooms are the six physical spaces the drawings show: the hospital
zones (one distribution transformer each) and the classrooms.

Topology is the profile's own parent chain. Hospital equipment hangs off its zone transformer and
names the campus service (circuit) it belongs to; classroom equipment hangs off its classroom, which
is the single room of one campus service. A wire in any drawing must be one of `edges()`.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.active_site import CATALOG, site_profile

# Ordered priority classes for the appliance-level optimizer (highest first). Class membership is
# derived from configuration (tier, essential flag) and, for classroom optional loads, from the
# room's session and activity evidence. Policies may only reorder the optional classes.
CRITICAL = "hospital_critical"            # essential equipment on T1 hospital services
ROOM_ESSENTIAL = "classroom_essential"    # each classroom's protected lighting and computers
ACTIVE = "classroom_active"               # optional loads, room has a session, evidence ACTIVE
UNKNOWN = "classroom_unknown"             # optional loads, room has a session, evidence UNKNOWN
SUPPORT = "hospital_support"              # non-essential hospital equipment (water pump, HVAC, fans)
INACTIVE = "classroom_inactive"           # optional loads, room has a session, evidence INACTIVE
IDLE = "classroom_idle"                   # optional loads in rooms with no session

PROTECTED_CLASSES = (CRITICAL, ROOM_ESSENTIAL)
CLASS_ORDER = {
    "activity_first": (CRITICAL, ROOM_ESSENTIAL, ACTIVE, UNKNOWN, SUPPORT, INACTIVE, IDLE),
    "water_first": (CRITICAL, ROOM_ESSENTIAL, SUPPORT, ACTIVE, UNKNOWN, INACTIVE, IDLE),
}
CLASS_LABELS = {
    CRITICAL: "Hospital critical (T1, protected)",
    ROOM_ESSENTIAL: "Classroom essential (protected minimum)",
    ACTIVE: "Classroom optional, session and ACTIVE evidence",
    UNKNOWN: "Classroom optional, session and UNKNOWN evidence",
    SUPPORT: "Hospital support (T2 water pump and HVAC)",
    INACTIVE: "Classroom optional, session and INACTIVE evidence",
    IDLE: "Classroom optional, no session",
}

SOURCE_ID = next(a.id for a in site_profile.assets if a.type.value == "source")
SOURCE_NAME = next(a.name for a in site_profile.assets if a.type.value == "source")


@dataclass(frozen=True)
class Appliance:
    id: str              # "<room>.<key>", unique across the site
    asset_id: str        # the site-profile asset id
    key: str             # equipment type key (drives the drawing's illustration)
    name: str
    room_id: str
    zone: str            # "hospital" | "classroom"
    feeder: str
    service_id: str      # campus service (circuit) the appliance decomposes
    distribution_id: str  # the room's distribution node in the topology (transformer or classroom)
    demand_w: int
    service_tier: str    # tier of the parent service, from the profile
    essential: bool      # from the profile; protected whatever the activity evidence says
    indivisible_group: str | None = None  # none are configured; supported by the optimizer
    requires: tuple = ()                  # none are configured; supported by the optimizer

    def static_class(self) -> str | None:
        if self.zone == "hospital":
            return CRITICAL if self.essential else SUPPORT
        return ROOM_ESSENTIAL if self.essential else None  # optional classroom loads depend on sessions


def _rooms():
    rooms = []
    for tx, zone in CATALOG.transformers.items():
        rooms.append({"id": zone, "name": zone, "zone": "hospital", "feeder": "A", "distribution_id": tx,
                      "distribution_name": CATALOG.transformer_names[tx], "service_id": None})
    for c in CATALOG.classrooms:
        svc = next(s for s in CATALOG.services if s["id"] == c["service_id"])
        rooms.append({"id": c["id"], "name": c["name"], "zone": "classroom", "feeder": svc["feeder"],
                      "distribution_id": c["id"], "distribution_name": f"{c['name']} panel", "service_id": svc["id"]})
    return rooms


ROOMS = _rooms()
ROOM_BY_ID = {r["id"]: r for r in ROOMS}


def _appliances() -> tuple[Appliance, ...]:
    services = {s["id"]: s for s in CATALOG.services}
    by_parent_key = {}
    for a in site_profile.assets:
        if a.type.value == "load":
            by_parent_key[(a.parent_id, a.load_key())] = a.id
    out = []
    for tx, zone in CATALOG.transformers.items():
        for key, name, watts, essential in CATALOG.hospital_loads[zone]:
            sid = CATALOG.hospital_parent[(zone, key)]
            out.append(Appliance(id=f"{zone}.{key}", asset_id=by_parent_key[(tx, key)], key=key, name=name,
                                 room_id=zone, zone="hospital", feeder=services[sid]["feeder"], service_id=sid,
                                 distribution_id=tx, demand_w=watts, service_tier=services[sid]["tier"],
                                 essential=essential))
    for c in CATALOG.classrooms:
        svc = services[c["service_id"]]
        for key, name, watts, essential in CATALOG.classroom_loads[c["id"]]:
            out.append(Appliance(id=f"{c['id']}.{key}", asset_id=by_parent_key[(c["id"], key)], key=key, name=name,
                                 room_id=c["id"], zone="classroom", feeder=svc["feeder"], service_id=svc["id"],
                                 distribution_id=c["id"], demand_w=watts, service_tier=svc["tier"],
                                 essential=essential))
    return tuple(out)


APPLIANCES = _appliances()
APPLIANCE_BY_ID = {a.id: a for a in APPLIANCES}
INDEX = {a.id: i for i, a in enumerate(APPLIANCES)}


def edges() -> list[dict]:
    """Every configured connection, source to appliance, following the profile's parent chain."""
    out = [{"id": f"{SOURCE_ID}>{f}", "from": SOURCE_ID, "to": f, "kind": "feeder"} for f in sorted(CATALOG.feeder_limits_w)]
    for room in ROOMS:
        if room["zone"] == "classroom":
            # Feeder -> service circuit -> classroom panel (the profile's chain: classroom under service under feeder).
            out.append({"id": f"{room['feeder']}>{room['service_id']}", "from": room["feeder"], "to": room["service_id"],
                        "kind": "circuit"})
            out.append({"id": f"{room['service_id']}>{room['id']}", "from": room["service_id"], "to": room["id"],
                        "kind": "distribution"})
        else:
            out.append({"id": f"{room['feeder']}>{room['distribution_id']}", "from": room["feeder"],
                        "to": room["distribution_id"], "kind": "distribution"})
    for a in APPLIANCES:
        out.append({"id": f"{a.distribution_id}>{a.id}", "from": a.distribution_id, "to": a.id, "kind": "branch"})
    return out


def path(appliance: Appliance) -> list[str]:
    """Node ids from the source to the appliance along configured edges."""
    room = ROOM_BY_ID[appliance.room_id]
    if room["zone"] == "classroom":
        return [SOURCE_ID, appliance.feeder, room["service_id"], room["id"], appliance.id]
    return [SOURCE_ID, appliance.feeder, appliance.distribution_id, appliance.id]


def catalog_problems() -> list[str]:
    """Integrity checks: unique ids, rooms, feeders, and leaf sums that match their parent services."""
    problems = []
    if len(INDEX) != len(APPLIANCES):
        problems.append("duplicate appliance ids")
    for a in APPLIANCES:
        if a.room_id not in ROOM_BY_ID:
            problems.append(f"{a.id}: unknown room {a.room_id}")
        if a.feeder not in CATALOG.feeder_limits_w:
            problems.append(f"{a.id}: unknown feeder {a.feeder}")
        if a.demand_w <= 0:
            problems.append(f"{a.id}: demand must be positive")
    for s in CATALOG.services:
        leaves = sum(a.demand_w for a in APPLIANCES if a.service_id == s["id"])
        if leaves != s["watts"]:
            problems.append(f"{s['id']}: appliances total {leaves} W, service rated {s['watts']} W")
    edge_ids = {e["id"] for e in edges()}
    for a in APPLIANCES:
        p = path(a)
        for src, dst in zip(p, p[1:]):
            if f"{src}>{dst}" not in edge_ids:
                problems.append(f"{a.id}: path hop {src}>{dst} is not a configured connection")
    return problems
