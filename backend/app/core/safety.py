"""Hard safety boundary between occupancy predictions and protected demand (#22).

Predictions may only reorder optional service. They can never remove protected demand:
hospital critical circuits and each classroom's essential minimum (lighting + computers).
This is a modeled policy, not certified electrical protection; it cannot create supply.
"""
from __future__ import annotations

from app.core.active_site import CATALOG

SAFETY_POLICY_VERSION = "safety-2026-10-10.1"

# Services that are protected whatever the activity model says: the site profile's T1 hospital services.
CAMPUS_PROTECTED_SERVICES = CATALOG.protected_services

# Downgrading a room to INACTIVE needs this many consecutive INACTIVE readings.
# Upgrades (to ACTIVE) and fallbacks (to UNKNOWN) apply at once: they never shed anything.
INACTIVE_CONFIRMATIONS = 2

VALID_STATES = ("ACTIVE", "UNKNOWN", "INACTIVE")

# A changed (guarded) state reorders optional loads only after it repeats on this many consecutive readings.
# Single-reading classifier errors therefore cannot switch loads back and forth. Readings without any valid
# evidence (failed inference, no score) skip the hold and fall back to UNKNOWN at once.
RANK_DWELL_READINGS = 3

FALLBACK_ORDER = (f"hospital critical ({', '.join(CAMPUS_PROTECTED_SERVICES)})", "classroom essentials in room rank order",
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


class RankDwell:
    """Hysteresis on the state used to rank optional loads; protected demand never depends on it."""

    def __init__(self, hold: int = RANK_DWELL_READINGS):
        self.hold = hold
        self._held: dict[str, str] = {}
        self._pending: dict[str, tuple[str, int]] = {}
        self._last_reading: dict[str, object] = {}
        self._out: dict[str, dict] = {}

    def reset(self, room=None):
        for store in (self._held, self._pending, self._last_reading, self._out):
            if room is None:
                store.clear()
            else:
                store.pop(room, None)

    def update(self, room: str, guarded: dict, reading_id) -> dict:
        if room in self._last_reading and self._last_reading[room] == reading_id:
            return dict(self._out[room])
        self._last_reading[room] = reading_id
        state = guarded["state"]
        held = self._held.get(room)
        no_evidence = state == "UNKNOWN" and guarded.get("score") is None
        if held is None or state == held or no_evidence:
            self._held[room] = state
            self._pending.pop(room, None)
        else:
            pending, count = self._pending.get(room, (state, 0))
            count = count + 1 if pending == state else 1
            self._pending[room] = (state, count)
            if count >= self.hold:
                self._held[room] = state
                self._pending.pop(room, None)
        out = dict(guarded)
        out["dwell"] = None
        if self._held[room] != state:
            out["state"] = self._held[room]
            out["dwell"] = (f"ranking keeps {self._held[room]} until {state} repeats on {self.hold} readings "
                            f"({self._pending[room][1]}/{self.hold})")
            out["guard"] = "; ".join(x for x in (guarded.get("guard"), out["dwell"]) if x)
        self._out[room] = out
        return dict(out)


def shortfall_status(protected_requested_w: int, protected_served_w: int) -> dict:
    """Quantified protected shortfall. Unmet protected demand is never reported as feasible."""
    shortfall = max(0, protected_requested_w - protected_served_w)
    return {"policy_version": SAFETY_POLICY_VERSION,
            "status": "PROTECTED_SHORTFALL" if shortfall else "FEASIBLE",
            "protected_requested_w": protected_requested_w,
            "protected_served_w": protected_served_w,
            "protected_shortfall_w": shortfall,
            "fallback_order": list(FALLBACK_ORDER)}
