"""Exact allocation for the six-service software catalog."""

def feasible(mask, services, capacity_w, feeder_limits, feeder_available):
    source = 0
    feeders = {"A": 0, "B": 0}
    for i, svc in enumerate(services):
        if not mask & (1 << i):
            continue
        feeder = svc["feeder"]
        source += svc["watts"]
        feeders[feeder] += svc["watts"]
        if not feeder_available.get(feeder, False) or feeders[feeder] > feeder_limits.get(feeder, 0):
            return False
    return source <= capacity_w


def allocate(services, capacity_w, feeder_limits, feeder_available, requested_mask,
             activity, previous_mask=0):
    """Enumerate every mask; score fixed critical loads before evidence-ranked rooms."""
    best = None
    best_score = None
    for mask in range(1 << len(services)):
        if mask & ~requested_mask or not feasible(mask, services, capacity_w, feeder_limits, feeder_available):
            continue
        served = lambda bit: int(bool(mask & (1 << bit)))
        active = sum(served(bit) for bit, cid in ((3, "CR1"), (4, "CR2"), (5, "CR3"))
                     if activity.get(cid, {}).get("state") == "ACTIVE")
        unknown = sum(served(bit) for bit, cid in ((3, "CR1"), (4, "CR2"), (5, "CR3"))
                      if activity.get(cid, {}).get("state") == "UNKNOWN")
        inactive = sum(served(bit) for bit, cid in ((3, "CR1"), (4, "CR2"), (5, "CR3"))
                       if activity.get(cid, {}).get("state") == "INACTIVE")
        watts = sum(s["watts"] for bit, s in enumerate(services) if served(bit))
        # L0/L1 are protected critical circuits (app.core.safety); evidence only orders requested
        # classrooms; the water pump follows ACTIVE and UNKNOWN rooms by explicit policy.
        # An INACTIVE prediction lowers a room's rank but never sheds it while capacity allows (#22).
        score = (served(0), served(1), active, unknown, served(2), inactive,
                 -((mask ^ previous_mask).bit_count()), watts, -mask)
        if best_score is None or score > best_score:
            best, best_score = mask, score
    return best or 0


def fixed_priority_mask(services, capacity_w, feeder_limits, feeder_available, requested_mask):
    """Fixed-order reference allocation over the same demand and physical limits."""
    order = (0, 1, 2, 3, 4, 5)
    mask = 0
    for bit in order:
        candidate = mask | (1 << bit)
        if requested_mask & (1 << bit) and feasible(candidate, services, capacity_w, feeder_limits, feeder_available):
            mask = candidate
    return mask
