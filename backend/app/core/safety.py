"""Hard safety boundary between occupancy predictions and protected demand (#22).

Predictions may only reorder optional service. They can never remove protected demand:
hospital critical circuits and each classroom's essential minimum (lighting + computers).
This is a modeled policy, not certified electrical protection; it cannot create supply.
"""
from __future__ import annotations

SAFETY_POLICY_VERSION = "safety-2026-10-10.1"

# Campus six-service catalog: services that are protected whatever the activity model says.
CAMPUS_PROTECTED_SERVICES = ("L0", "L1")
# Each classroom's essential minimum, shared by the campus and classroom-demo catalogs.
ROOM_ESSENTIAL_LOADS = ("lighting", "computers")

# Downgrading a room to INACTIVE needs this many consecutive INACTIVE readings.
# Upgrades (to ACTIVE) and fallbacks (to UNKNOWN) apply at once: they never shed anything.
INACTIVE_CONFIRMATIONS = 2

VALID_STATES = ("ACTIVE", "UNKNOWN", "INACTIVE")

FALLBACK_ORDER = ("hospital critical (L0, L1)", "classroom essentials in room rank order",
                  "optional loads in room rank order")


def normalize_prediction(prediction) -> dict:
    """Any failed, missing, malformed or out-of-range inference becomes UNKNOWN with a reason."""
    if not isinstance(prediction, dict):
        return {"state": "UNKNOWN", "score": None, "reason": "inference failed: no prediction",
                "model_version": "unavailable"}
    state = prediction.get("state")
    score = prediction.get("score")
    out = dict(prediction)
    if state not in VALID_STATES:
        out.update(state="UNKNOWN", score=None, reason=f"invalid prediction state {state!r}")
    elif state != "UNKNOWN" and (not isinstance(score, (int, float)) or isinstance(score, bool)
                                 or not 0.0 <= float(score) <= 1.0):
        out.update(state="UNKNOWN", score=None, reason="prediction without a valid score")
    out.setdefault("reason", "")
    out.setdefault("model_version", "unavailable")
    return out


class ActivityGuard:
    """Turns raw per-reading predictions into the state the allocator may use.

    INACTIVE must be seen on INACTIVE_CONFIRMATIONS consecutive distinct readings before it
    lowers a room's priority; until then the room is UNKNOWN with a visible guard reason.
    """

    def __init__(self, confirmations: int = INACTIVE_CONFIRMATIONS):
        self.confirmations = confirmations
        self._streak: dict[str, int] = {}
        self._last_reading: dict[str, object] = {}
        self._effective: dict[str, dict] = {}

    def reset(self, room=None):
        for store in (self._streak, self._last_reading, self._effective):
            if room is None:
                store.clear()
            else:
                store.pop(room, None)

    def update(self, room: str, prediction, reading_id) -> dict:
        """Feed one prediction for a distinct reading; repeated reading_ids are not re-counted."""
        if room in self._last_reading and self._last_reading[room] == reading_id:
            return dict(self._effective[room])
        self._last_reading[room] = reading_id
        raw = normalize_prediction(prediction)
        if raw["state"] == "INACTIVE":
            self._streak[room] = self._streak.get(room, 0) + 1
        else:
            self._streak[room] = 0
        effective = dict(raw)
        effective["raw_state"] = raw["state"]
        effective["guard"] = None
        if raw["state"] == "INACTIVE" and self._streak[room] < self.confirmations:
            effective.update(state="UNKNOWN",
                             guard=f"INACTIVE not yet confirmed ({self._streak[room]}/{self.confirmations} readings); "
                                   "treated as UNKNOWN")
        elif raw["state"] == "UNKNOWN":
            effective["guard"] = f"conservative fallback: {raw['reason'] or 'no usable evidence'}"
        self._effective[room] = effective
        return dict(effective)

    def get(self, room: str):
        value = self._effective.get(room)
        return None if value is None else dict(value)


def shortfall_status(protected_requested_w: int, protected_served_w: int) -> dict:
    """Quantified protected shortfall. Unmet protected demand is never reported as feasible."""
    shortfall = max(0, protected_requested_w - protected_served_w)
    return {"policy_version": SAFETY_POLICY_VERSION,
            "status": "PROTECTED_SHORTFALL" if shortfall else "FEASIBLE",
            "protected_requested_w": protected_requested_w,
            "protected_served_w": protected_served_w,
            "protected_shortfall_w": shortfall,
            "fallback_order": list(FALLBACK_ORDER)}
