"""Versioned site profiles (#26): one validated JSON file defines the inventory, topology and presets.

A profile is checked completely before anything runs: schema (strict types, units, ranges) first,
then topology and parent/leaf watt accounting. Every problem is reported with the asset it concerns,
so a bad file fails at startup with a list of fixes instead of a half-built site.

Sensitive RFID enrollment never lives in a profile; see load_rfid_enrollment().
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# The controller's exact allocator enumerates every service mask and the radio command mask has 9 bits.
MAX_SERVICES = 9
LED_BITS = range(9)
MAX_WATTS = 1_000_000
# The controller models a two-feeder radial campus: feeder A serves the hospital, feeder B the classrooms.
ZONE_FEEDER = {"hospital": "A", "classroom": "B"}


class AssetType(str, Enum):
    SOURCE = "source"
    FEEDER = "feeder"
    SERVICE = "service"
    HOSPITAL_ROOM = "hospital_room"
    CLASSROOM = "classroom"
    LOAD = "load"
    TRANSFORMER = "transformer"


class Tier(str, Enum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


Watts = Optional[int]


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    type: AssetType
    name: str = Field(min_length=1, max_length=120)
    parent_id: Optional[str] = None
    capacity_w: Watts = Field(None, ge=0, le=MAX_WATTS)
    rating_w: Watts = Field(None, ge=0, le=MAX_WATTS)
    rated_current_a: Optional[float] = Field(None, gt=0, le=10_000, allow_inf_nan=False)
    tier: Optional[Tier] = None
    zone: Optional[str] = Field(None, min_length=1, max_length=64)
    led_bit: Optional[int] = Field(None, ge=LED_BITS.start, lt=LED_BITS.stop)
    coords: Optional[Coordinates] = None
    policy_refs: Optional[List[str]] = None
    essential: Optional[bool] = None
    # load: short key unique within its parent (defaults to the id without its "L_<parent>_" prefix)
    key: Optional[str] = Field(None, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    # hospital load: the campus service whose watts it decomposes
    service_id: Optional[str] = None
    # classroom: the room letter board A reports for its card reader/buttons
    hardware_room: Optional[str] = Field(None, pattern=r"^[A-Z]$")
    # feeder: the "shortage" preset of the zone view it serves
    shortage_preset_w: Watts = Field(None, ge=0, le=MAX_WATTS)

    def load_key(self) -> str:
        if self.key:
            return self.key
        prefix = f"L_{self.parent_id}_"
        return self.id[len(prefix):] if self.id.startswith(prefix) else self.id


PARENT_TYPES = {
    AssetType.SOURCE: (),
    AssetType.FEEDER: (AssetType.SOURCE,),
    AssetType.SERVICE: (AssetType.FEEDER,),
    AssetType.CLASSROOM: (AssetType.SERVICE,),
    AssetType.HOSPITAL_ROOM: (AssetType.SERVICE,),
    AssetType.TRANSFORMER: (AssetType.FEEDER,),
    AssetType.LOAD: (AssetType.CLASSROOM, AssetType.TRANSFORMER),
}
REQUIRED = {
    AssetType.SOURCE: ("capacity_w",),
    AssetType.FEEDER: ("capacity_w",),
    AssetType.SERVICE: ("rating_w", "tier", "zone"),
    AssetType.CLASSROOM: ("led_bit",),
    AssetType.HOSPITAL_ROOM: ("led_bit",),
    AssetType.TRANSFORMER: ("zone",),
    AssetType.LOAD: ("rating_w", "essential"),
}
# Fields that would mean something else (or a wrong unit) on this asset type.
ALLOWED_EXTRA = {
    AssetType.SOURCE: (),
    AssetType.FEEDER: ("shortage_preset_w",),
    AssetType.SERVICE: (),
    AssetType.CLASSROOM: ("hardware_room",),
    AssetType.HOSPITAL_ROOM: (),
    AssetType.TRANSFORMER: ("rated_current_a",),
    AssetType.LOAD: ("key", "service_id"),
}
TYPED_FIELDS = ("capacity_w", "rating_w", "rated_current_a", "tier", "led_bit", "essential", "key", "service_id",
                "hardware_room", "shortage_preset_w")
UNIT_HINTS = {(AssetType.TRANSFORMER, "rating_w"): "transformer ratings are amps: use rated_current_a",
              (AssetType.SERVICE, "capacity_w"): "a service declares its demand as rating_w",
              (AssetType.LOAD, "capacity_w"): "a load declares its demand as rating_w",
              (AssetType.FEEDER, "rating_w"): "a feeder declares its limit as capacity_w",
              (AssetType.SOURCE, "rating_w"): "a source declares its limit as capacity_w"}


class SiteProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    # hospital zone a fault is injected into when a request names none
    fault_zone: Optional[str] = None
    assets: List[Asset] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_topology(self):
        problems = site_problems(self)
        if problems:
            raise ValueError(f"{len(problems)} problem(s): " + "; ".join(problems))
        return self


def site_problems(profile: SiteProfile) -> list[str]:
    """Every topology, unit and accounting problem in a schema-valid profile, one line per fix."""
    problems: list[str] = []
    by_id: dict[str, Asset] = {}
    for a in profile.assets:
        if a.id in by_id:
            problems.append(f"Duplicate Asset ID: {a.id}")
        by_id[a.id] = a
    for a in profile.assets:
        if a.parent_id is not None and a.parent_id not in by_id:
            problems.append(f"Dangling parent_id: {a.parent_id} for asset {a.id}")
    for a in profile.assets:
        seen, cur = {a.id}, a
        while cur.parent_id in by_id:
            if cur.parent_id in seen:
                problems.append(f"Cycle detected involving asset {a.id}")
                break
            seen.add(cur.parent_id)
            cur = by_id[cur.parent_id]
    if problems:
        return problems  # later checks walk the tree

    for a in profile.assets:
        parent = by_id.get(a.parent_id) if a.parent_id else None
        allowed = PARENT_TYPES[a.type]
        if allowed and (parent is None or parent.type not in allowed):
            problems.append(f"{a.id}: a {a.type.value} must sit under a {' or '.join(t.value for t in allowed)}"
                            f" (parent_id is {a.parent_id!r})")
        if not allowed and parent is not None:
            problems.append(f"{a.id}: a {a.type.value} has no parent")
        for field in REQUIRED[a.type]:
            if getattr(a, field) is None:
                problems.append(f"{a.id}: {a.type.value} requires {field}")
        for field in TYPED_FIELDS:
            if getattr(a, field) is not None and field not in REQUIRED[a.type] and field not in ALLOWED_EXTRA[a.type]:
                hint = UNIT_HINTS.get((a.type, field), f"not used by a {a.type.value}")
                problems.append(f"{a.id}: {field} is not allowed ({hint})")
    if problems:
        return problems

    kinds = {t: [a for a in profile.assets if a.type == t] for t in AssetType}
    children: dict[str, list[Asset]] = {}
    for a in profile.assets:
        if a.parent_id:
            children.setdefault(a.parent_id, []).append(a)

    if len(kinds[AssetType.SOURCE]) != 1:
        problems.append(f"exactly one source is required, found {len(kinds[AssetType.SOURCE])}")
    feeders = {f.id: f for f in kinds[AssetType.FEEDER]}
    if set(feeders) != set(ZONE_FEEDER.values()):
        problems.append(f"feeders must be exactly {sorted(ZONE_FEEDER.values())} (A hospital, B classroom), "
                        f"found {sorted(feeders)}")
    services = kinds[AssetType.SERVICE]
    if not 1 <= len(services) <= MAX_SERVICES:
        problems.append(f"between 1 and {MAX_SERVICES} services are supported, found {len(services)}")
    for s in services:
        if s.zone not in ZONE_FEEDER:
            problems.append(f"{s.id}: service zone must be one of {sorted(ZONE_FEEDER)}, not {s.zone!r}")
        elif s.parent_id != ZONE_FEEDER[s.zone]:
            problems.append(f"{s.id}: {s.zone} services belong on feeder {ZONE_FEEDER[s.zone]}, not {s.parent_id}")

    for parent_type, child_type in ((AssetType.SOURCE, AssetType.FEEDER), (AssetType.FEEDER, AssetType.SERVICE)):
        for p in kinds[parent_type]:
            total = sum(c.capacity_w if child_type == AssetType.FEEDER else c.rating_w
                        for c in children.get(p.id, []) if c.type == child_type)
            if total > p.capacity_w:
                problems.append(f"Asset {p.id} capacity {p.capacity_w} exceeded by children total {total}")
    for f in feeders.values():
        if f.shortage_preset_w is not None and f.shortage_preset_w > f.capacity_w:
            problems.append(f"{f.id}: shortage_preset_w {f.shortage_preset_w} exceeds capacity_w {f.capacity_w}")

    for kind in (AssetType.CLASSROOM, AssetType.HOSPITAL_ROOM):
        for a in kinds[kind]:
            if by_id[a.parent_id].zone != kind.value.split("_")[0]:
                problems.append(f"{a.id}: a {kind.value} must sit under a {kind.value.split('_')[0]} service")
    bits: dict[int, str] = {}
    letters: dict[str, str] = {}
    for a in kinds[AssetType.CLASSROOM] + kinds[AssetType.HOSPITAL_ROOM]:
        if a.led_bit in bits:
            problems.append(f"{a.id}: led_bit {a.led_bit} already used by {bits[a.led_bit]}")
        bits[a.led_bit] = a.id
        if a.hardware_room:
            if a.hardware_room in letters:
                problems.append(f"{a.id}: hardware_room {a.hardware_room} already used by {letters[a.hardware_room]}")
            letters[a.hardware_room] = a.id

    zones: dict[str, str] = {}
    for t in kinds[AssetType.TRANSFORMER]:
        if t.parent_id != ZONE_FEEDER["hospital"]:
            problems.append(f"{t.id}: hospital transformers sit on feeder {ZONE_FEEDER['hospital']}")
        if t.zone in zones:
            problems.append(f"{t.id}: zone {t.zone} already served by {zones[t.zone]}")
        zones[t.zone] = t.id
    if profile.fault_zone is not None and profile.fault_zone not in zones:
        problems.append(f"fault_zone {profile.fault_zone!r} is not a transformer zone ({sorted(zones)})")

    keys: set[tuple[str, str]] = set()
    leaf_w = {s.id: 0 for s in services}
    for load in kinds[AssetType.LOAD]:
        key = (load.parent_id, load.load_key())
        if key in keys:
            problems.append(f"{load.id}: load key {key[1]!r} repeats under {load.parent_id}")
        keys.add(key)
        parent = by_id[load.parent_id]
        if parent.type == AssetType.CLASSROOM:
            if load.service_id is not None:
                problems.append(f"{load.id}: classroom loads take their service from the classroom; drop service_id")
            leaf_w[parent.parent_id] += load.rating_w
            continue
        service = by_id.get(load.service_id) if load.service_id else None
        if service is None or service.type != AssetType.SERVICE or service.zone != "hospital":
            problems.append(f"{load.id}: hospital loads need service_id naming a hospital service "
                            f"(got {load.service_id!r})")
            continue
        leaf_w[service.id] += load.rating_w
        if load.essential != (service.tier == Tier.T1):
            problems.append(f"{load.id}: essential={load.essential} but {service.id} is {service.tier.value}; "
                            "essential equipment belongs to T1 services only")

    rooms_by_service: dict[str, list[str]] = {}
    for c in kinds[AssetType.CLASSROOM]:
        rooms_by_service.setdefault(c.parent_id, []).append(c.id)
    for s in services:
        if s.zone == "classroom":
            rooms = rooms_by_service.get(s.id, [])
            if len(rooms) != 1:
                problems.append(f"{s.id}: a classroom service decomposes into exactly one classroom, found {rooms}")
        if s.zone in ZONE_FEEDER and leaf_w[s.id] != s.rating_w:
            problems.append(f"{s.id}: leaf loads total {leaf_w[s.id]} W but the service is rated {s.rating_w} W")
    if any(s.zone == "hospital" for s in services) and not zones:
        problems.append("hospital services need at least one transformer zone for their equipment")
    return problems


class SiteProfileError(ValueError):
    """A profile file that cannot be activated; str() lists every fix, one per line."""

    def __init__(self, path: str, problems: list[str]):
        self.path = path
        self.problems = problems
        super().__init__(f"site profile {path} is invalid:\n" + "\n".join(f"  - {p}" for p in problems))


def _diagnostics(path: str, data, exc: ValidationError) -> list[str]:
    lines = []
    assets = data.get("assets") if isinstance(data, dict) else None
    for err in exc.errors():
        loc = list(err["loc"])
        where = ".".join(str(p) for p in loc) or "profile"
        if len(loc) >= 2 and loc[0] == "assets" and isinstance(loc[1], int) and isinstance(assets, list) \
                and loc[1] < len(assets) and isinstance(assets[loc[1]], dict):
            field = ".".join(str(p) for p in loc[2:]) or "asset"
            where = f"{assets[loc[1]].get('id', f'assets[{loc[1]}]')}.{field}"
        msg = err["msg"]
        if err["type"] == "value_error":
            msg = msg.removeprefix("Value error, ")
            if " problem(s): " in msg:
                lines.extend(msg.split(" problem(s): ", 1)[1].split("; "))
                continue
        lines.append(f"{where}: {msg}")
    return lines


def parse_site_profile(text: str, path: str = "<profile>") -> SiteProfile:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise SiteProfileError(path, [f"not valid JSON: {exc}"]) from None
    try:
        return SiteProfile.model_validate_json(text)
    except ValidationError as exc:
        raise SiteProfileError(path, _diagnostics(path, data, exc)) from None


def load_site_profile(path: str) -> SiteProfile:
    with open(path, "r", encoding="utf-8") as f:
        return parse_site_profile(f.read(), path)


class RfidEnrollment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tag_to_room: Dict[str, str]


def load_rfid_enrollment(path: str, local_path: str | None = None) -> RfidEnrollment:
    """Card UIDs are private: an untracked `<name>.local.json` beside the tracked placeholder file wins."""
    local_path = local_path or path.removesuffix(".json") + ".local.json"
    with open(local_path if os.path.exists(local_path) else path, "r", encoding="utf-8") as f:
        return RfidEnrollment.model_validate_json(f.read())


def get_config_hash(profile: SiteProfile) -> str:
    """Stable hash of the profile's validated content; recorded with every run identity and decision."""
    data = json.dumps(profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class SiteCatalog:
    """Read-only lookups the controller and views derive from one validated profile."""
    name: str
    version: str
    config_hash: str
    source_capacity_w: int
    feeder_limits_w: dict
    feeder_presets_w: dict
    services: list
    classrooms: list
    hospital_rooms: list
    classroom_loads: dict
    hospital_zones: tuple
    hospital_loads: dict
    hospital_parent: dict
    transformers: dict
    transformer_ratings_a: dict
    transformer_names: dict
    protected_services: tuple
    fault_zone: Optional[str]


def build_catalog(profile: SiteProfile) -> SiteCatalog:
    kinds = {t: [a for a in profile.assets if a.type == t] for t in AssetType}
    source = kinds[AssetType.SOURCE][0]
    services = [{"id": a.id, "name": a.name, "tier": a.tier.value, "feeder": a.parent_id, "watts": a.rating_w,
                 "zone": a.zone} for a in kinds[AssetType.SERVICE]]
    classrooms = [{"id": a.id, "name": a.name, "service_id": a.parent_id, "led_bit": a.led_bit,
                   "hardware_room": a.hardware_room} for a in kinds[AssetType.CLASSROOM]]
    hospital_rooms = [{"id": a.id, "name": a.name, "lighting_service": a.parent_id, "led_bit": a.led_bit}
                      for a in kinds[AssetType.HOSPITAL_ROOM]]
    transformers = {a.id: a.zone for a in kinds[AssetType.TRANSFORMER]}
    classroom_loads = {c["id"]: [] for c in classrooms}
    hospital_loads = {zone: [] for zone in transformers.values()}
    hospital_parent = {}
    for load in kinds[AssetType.LOAD]:
        row = (load.load_key(), load.name, load.rating_w, load.essential)
        if load.parent_id in classroom_loads:
            classroom_loads[load.parent_id].append(row)
        else:
            zone = transformers[load.parent_id]
            hospital_loads[zone].append(row)
            hospital_parent[(zone, row[0])] = load.service_id
    zones = tuple(transformers.values())
    return SiteCatalog(
        name=profile.name, version=profile.version, config_hash=get_config_hash(profile),
        source_capacity_w=source.capacity_w,
        feeder_limits_w={f.id: f.capacity_w for f in kinds[AssetType.FEEDER]},
        feeder_presets_w={f.id: f.shortage_preset_w for f in kinds[AssetType.FEEDER]},
        services=services, classrooms=classrooms, hospital_rooms=hospital_rooms,
        classroom_loads=classroom_loads, hospital_zones=zones, hospital_loads=hospital_loads,
        hospital_parent=hospital_parent, transformers=transformers,
        transformer_ratings_a={a.id: a.rated_current_a for a in kinds[AssetType.TRANSFORMER]},
        transformer_names={a.id: a.name for a in kinds[AssetType.TRANSFORMER]},
        protected_services=tuple(s["id"] for s in services if s["tier"] == "T1" and s["zone"] == "hospital"),
        fault_zone=profile.fault_zone or (zones[0] if zones else None))


def main(argv: list[str] | None = None) -> int:
    """`python -m app.core.config <profile.json>...` validates profiles without starting the server."""
    import sys
    paths = sys.argv[1:] if argv is None else argv
    if not paths:
        print("usage: python -m app.core.config <profile.json> [...]", file=sys.stderr)
        return 2
    status = 0
    for path in paths:
        try:
            catalog = build_catalog(load_site_profile(path))
        except (OSError, SiteProfileError) as exc:
            print(exc, file=sys.stderr)
            status = 1
            continue
        print(f"{path}: OK  {catalog.name} v{catalog.version}  hash {catalog.config_hash}  "
              f"{len(catalog.services)} services, {len(catalog.classrooms)} classrooms, "
              f"{len(catalog.hospital_zones)} hospital zones")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
