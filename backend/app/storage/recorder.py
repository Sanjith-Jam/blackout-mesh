import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid4

def utc(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

class HistoryRecorder:
    def __init__(self, store, run_id=None, clock=time.monotonic):
        self.store = store
        self.run_id = run_id or str(uuid4())
        self.clock = clock
        self.last_sample = None
        self.signature = None
        self.pending_events = []
        self.counter = 0

    def event(self, event, inputs):
        self.store.append("campus", self.run_id, "event", event.event_id,
                          utc(datetime.fromisoformat(event.timestamp)), event.revision,
                          {"event": event.model_dump(), "inputs": inputs})
        self.pending_events.append(event.event_id)

    def capture(self, snapshot, inputs):
        data = snapshot.model_dump(mode="json")
        signature_data = {k: v for k, v in data.items() if k not in ("generated_at", "events", "replay")}
        signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
        timestamp = utc(snapshot.generated_at)
        if signature != self.signature:
            self.counter += 1
            decision_id = f"{self.run_id}:decision:{self.counter}"
            self.store.append("campus", self.run_id, "decision", decision_id,
                              timestamp, snapshot.control_revision,
                              {"snapshot": data, "inputs": inputs, "policy": data["allocation"],
                               "model": data["model"], "event_ids": list(self.pending_events),
                               "trail": {"incident_ids": list(self.pending_events),
                                         "observation": data["activity"],
                                         "decision_id": decision_id,
                                         "applied_transition": {"modeled_mask": data["modeled_mask"],
                                                                "proposed_mask": data["proposed_mask"]},
                                         "command_identity": None, "validated_ack": None}})
            self.signature = signature
            self.pending_events.clear()
        now = self.clock()
        if self.last_sample is None or now - self.last_sample >= 1:
            self.counter += 1
            self.store.append("campus", self.run_id, "telemetry", f"{self.run_id}:sample:{self.counter}",
                              timestamp, snapshot.control_revision,
                              {"capacity": data["source"]["capacity_w"],
                               "demand": sum(s["watts"] for s in data["services"] if s["requested"]),
                               "servedCount": sum(s["modeled_served"] for s in data["services"]),
                               "shedCount": sum(s["requested"] and not s["modeled_served"] for s in data["services"])})
            self.last_sample = now

