"""Canonical power-path edges for the drawings (#23).

Every wire in a drawing maps to one edge here. An edge separates topology (is the path closed?),
the allocator's command, the modeled applied state after staged restoration, any observed sensor
evidence, and physical confirmation (no hardware is connected, so it is always NOT_CONNECTED).
Watts are modeled allocation quantities, not measured current.
"""
from __future__ import annotations

ENERGIZED = "ENERGIZED"              # applied in the model and the path is closed
PENDING = "PENDING_RESTORATION"      # commanded, waiting for the restoration gate
SHED = "SHED"                        # not commanded by the allocator
OPEN = "OPEN"                        # topology open upstream: nothing can flow
UNKNOWN = "UNKNOWN"                  # evidence missing or abstained: do not show as healthy

STATES = (ENERGIZED, PENDING, SHED, OPEN, UNKNOWN)


def edge(edge_id: str, src: str, dst: str, *, connected: bool, commanded: bool, applied: bool,
         requested_w: int, served_w: int, reason: str, observed: dict | None = None,
         evidence_unknown: bool = False) -> dict:
    if not connected:
        state = OPEN
    elif evidence_unknown:
        state = UNKNOWN
    elif applied:
        state = ENERGIZED
    elif commanded:
        state = PENDING
    else:
        state = SHED
    out = {"id": edge_id, "from": src, "to": dst, "state": state,
           "connected": connected, "commanded": commanded, "applied": applied and connected,
           "requested_w": requested_w, "served_w": served_w if connected else 0, "unit": "W",
           "provenance": "MODELED", "physical": "NOT_CONNECTED", "reason": reason}
    if observed is not None:
        out["observed"] = observed
    return out
