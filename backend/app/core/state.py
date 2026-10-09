import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any

from app.schemas.snapshot import (
    SystemSnapshot, SourceInfo, SourceKind, HardwareLinkStatus,
    ServiceSnapshot, Tier, FacilityZones, HospitalZone, HospitalRoom,
    ClassroomZone, ClassroomInfo, RfidReaderStatus, RfidEventType
)

SERVICE_CATALOG = [
    {"id": "L0", "name": "Hospital Essential Circuit", "tier": "T1", "feeder": "A", "watts": 2000, "zone": "hospital"},
    {"id": "L1", "name": "Emergency Lighting", "tier": "T1", "feeder": "A", "watts": 1000, "zone": "hospital"},
    {"id": "L2", "name": "Water Pump", "tier": "T2", "feeder": "A", "watts": 3000, "zone": "hospital"},
    {"id": "L3", "name": "Classroom 1", "tier": "T2", "feeder": "B", "watts": 2000, "zone": "classroom"},
    {"id": "L4", "name": "Classroom 2", "tier": "T2", "feeder": "B", "watts": 2000, "zone": "classroom"},
    {"id": "L5", "name": "Classroom 3", "tier": "T3", "feeder": "B", "watts": 4000, "zone": "classroom"},
]

HOSPITAL_ROOMS = [
    {"id": "HR1", "name": "Hospital Room 1", "lighting_service": "L0", "led_bit": 0},
    {"id": "HR2", "name": "Hospital Room 2", "lighting_service": "L0", "led_bit": 1},
    {"id": "HR3", "name": "Hospital Room 3", "lighting_service": "L0", "led_bit": 2},
]

CLASSROOMS = [
    {"id": "CR1", "name": "Classroom 1", "service_id": "L3", "led_bit": 3},
    {"id": "CR2", "name": "Classroom 2", "service_id": "L4", "led_bit": 4},
    {"id": "CR3", "name": "Classroom 3", "service_id": "L5", "led_bit": 5},
]

# Configurable RFID UID mapping. Replace with real UIDs during hardware registration.
DEFAULT_RFID_MAP = {
    "CARD_1_UID": "CR1",
    "CARD_2_UID": "CR2",
    "CARD_3_UID": "CR3",
}

RFID_SCAN_COOLDOWN_SECONDS = 2.0
TIER_PRIORITY = {"T1": 0, "T2": 1, "T3": 2}

class GridState:
    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(GridState, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._lock = threading.RLock()
        self.source_capacity_w = 14000
        self.feeder_limits_w = {"A": 6000, "B": 8000}
        self.feeder_available = {"A": True, "B": True}
        self.control_revision = 0
        self.active_classroom_id = None
        self.recent_rfid_scan = None
        self.last_rfid_scan_time = None
        self.last_rfid_uid = None
        self.classroom_load_events = {"CR1": False, "CR2": False, "CR3": False}
        self.rfid_map = DEFAULT_RFID_MAP.copy()
        self.indicator_confirmed_mask = None
        self._initialized = True

    def process_rfid_scan(self, uid: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        with self._lock:
            now = time.time()
            if self.last_rfid_uid == uid and self.last_rfid_scan_time is not None:
                if now - self.last_rfid_scan_time < RFID_SCAN_COOLDOWN_SECONDS:
                    self.last_rfid_scan_time = now
                    return RfidEventType.DUPLICATE_SUPPRESSED.value, None, None, None
            
            self.last_rfid_uid = uid
            self.last_rfid_scan_time = now
            self.recent_rfid_scan = uid

            classroom_id = self.rfid_map.get(uid)
            if not classroom_id:
                self.active_classroom_id = None
                self.control_revision += 1
                return RfidEventType.UNKNOWN_CARD.value, None, None, None

            self.active_classroom_id = classroom_id
            self.control_revision += 1
            
            classroom = next((c for c in CLASSROOMS if c["id"] == classroom_id), None)
            if classroom:
                return RfidEventType.CARD_RECOGNIZED.value, classroom_id, classroom["name"], classroom["service_id"]
            return RfidEventType.CARD_RECOGNIZED.value, classroom_id, None, None

    def set_capacity(self, capacity_w: int):
        with self._lock:
            self.source_capacity_w = capacity_w
            self.control_revision += 1

    def set_feeder(self, feeder: str, available: bool):
        with self._lock:
            if feeder in self.feeder_available:
                self.feeder_available[feeder] = available
                self.control_revision += 1

    def set_classroom_load(self, classroom_id: str, active: bool):
        with self._lock:
            if classroom_id in self.classroom_load_events:
                self.classroom_load_events[classroom_id] = active
                self.control_revision += 1

    def compute_allocation(self) -> int:
        with self._lock:
            sorted_services = sorted(SERVICE_CATALOG, key=lambda s: (TIER_PRIORITY[s["tier"]], s["watts"]))
            modeled_mask = 0
            used_source = 0
            used_feeder = {"A": 0, "B": 0}
            
            for svc in sorted_services:
                f = svc["feeder"]
                w = svc["watts"]
                
                # Check constraints
                if not self.feeder_available.get(f, False):
                    continue
                if used_source + w > self.source_capacity_w:
                    continue
                if used_feeder[f] + w > self.feeder_limits_w.get(f, 0):
                    continue
                    
                # Allocate
                used_source += w
                used_feeder[f] += w
                bit = int(svc["id"][1:])
                modeled_mask |= (1 << bit)
                
            return modeled_mask

    def compute_indicator_command_mask(self, modeled_mask: int) -> int:
        with self._lock:
            mask = 0
            # Hospital rooms L0
            l0_served = bool((modeled_mask >> 0) & 1)
            if l0_served:
                for room in HOSPITAL_ROOMS:
                    mask |= (1 << room["led_bit"])
                    
            # Classroom logic
            if self.active_classroom_id:
                classroom = next((c for c in CLASSROOMS if c["id"] == self.active_classroom_id), None)
                if classroom:
                    cr_svc = classroom["service_id"]
                    svc_bit = int(cr_svc[1:])
                    svc_served = bool((modeled_mask >> svc_bit) & 1)
                    load_active = self.classroom_load_events.get(self.active_classroom_id, False)
                    
                    cr_svc_obj = next((s for s in SERVICE_CATALOG if s["id"] == cr_svc), None)
                    feeder_avail = False
                    if cr_svc_obj:
                        feeder_avail = self.feeder_available.get(cr_svc_obj["feeder"], False)
                    
                    if svc_served and load_active and feeder_avail:
                        mask |= (1 << classroom["led_bit"])
                        
            return mask

    def build_snapshot(self) -> SystemSnapshot:
        with self._lock:
            modeled_mask = self.compute_allocation()
            indicator_command = self.compute_indicator_command_mask(modeled_mask)
            requested_mask = 0b111111 # Assuming all connected services are implicitly requesting
            
            services_out = []
            for svc in SERVICE_CATALOG:
                bit = int(svc["id"][1:])
                served = bool((modeled_mask >> bit) & 1)
                
                reason = "Served (Priority/Capacity Match)" if served else "Capacity or Feeder Limit Exceeded"
                services_out.append(ServiceSnapshot(
                    id=svc["id"],
                    name=svc["name"],
                    tier=Tier(svc["tier"]),
                    feeder=svc["feeder"],
                    watts=svc["watts"],
                    requested=True,
                    modeled_served=served,
                    indicator_confirmed=None,
                    model_reason=reason
                ))

            hospital_rooms = [
                HospitalRoom(id=r["id"], name=r["name"], lighting_service=r["lighting_service"], led_bit=r["led_bit"])
                for r in HOSPITAL_ROOMS
            ]
            
            classroom_infos = []
            for c in CLASSROOMS:
                cid = c["id"]
                is_registered = any(v == cid for v in self.rfid_map.values())
                cinfo = ClassroomInfo(
                    id=cid,
                    name=c["name"],
                    service_id=c["service_id"],
                    rfid_card_registered=is_registered,
                    led_bit=c["led_bit"],
                    load_event_active=self.classroom_load_events.get(cid, False)
                )
                classroom_infos.append(cinfo)
            
            zones = FacilityZones(
                hospital=HospitalZone(rooms=hospital_rooms),
                classroom=ClassroomZone(
                    active_classroom_id=self.active_classroom_id,
                    recent_rfid_scan=self.recent_rfid_scan,
                    rfid_reader_status=RfidReaderStatus.NOT_CONNECTED,
                    classrooms=classroom_infos
                )
            )

            return SystemSnapshot(
                control_revision=self.control_revision,
                generated_at=datetime.now(timezone.utc),
                source=SourceInfo(kind=SourceKind.SIMULATED, capacity_w=self.source_capacity_w),
                feeder_limits_w=self.feeder_limits_w.copy(),
                requested_mask=requested_mask,
                modeled_mask=modeled_mask,
                indicator_mask=None,
                indicator_command_mask=indicator_command,
                indicator_confirmed_mask=self.indicator_confirmed_mask,
                zones=zones,
                hardware_link=HardwareLinkStatus.NOT_CONNECTED,
                services=services_out
            )
