"""Exact allocation for the six-service software catalog."""

def feasible(mask, services, capacity_w, feeder_limits, feeder_available):
    source = 0
    feeders = {svc["feeder"]: 0 for svc in services}
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
             activity, previous_mask=0, policy=None, waiting_s=None):
    """Exact lexicographic optimization; immutable T1 protection precedes soft preferences."""
    from app.core.policy import AllocationPolicy, score
    policy = policy or AllocationPolicy()
    if len(services) > 20:
        raise ValueError("exact allocator supports at most 20 services")
    best, best_score = 0, None
    for mask in range(1 << len(services)):
        if mask & ~requested_mask or not feasible(mask, services, capacity_w, feeder_limits, feeder_available):
            continue
        candidate, _ = score(mask, services, activity, previous_mask, policy, waiting_s or {})
        if best_score is None or candidate > best_score:
            best, best_score = mask, candidate
    return best


def explain(services, capacity_w, feeder_limits, feeder_available, requested_mask,
            activity, previous_mask, policy, waiting_s, proposed_mask, applied_mask):
    """Replay input and explicit force-on counterfactuals for every requested load."""
    import hashlib
    import json
    from app.core.policy import score
    inputs = dict(services=services, capacity_w=capacity_w, feeder_limits=feeder_limits,
                  feeder_available=feeder_available, requested_mask=requested_mask, activity=activity,
                  previous_mask=previous_mask, policy=policy.model_dump(), waiting_s=waiting_s)
    inputs = json.loads(json.dumps(inputs))  # Detach replay evidence from live mutable application state.
    _, terms = score(proposed_mask, services, activity, previous_mask, policy, waiting_s)
    decisions = []
    for bit, svc in enumerate(services):
        requested, proposed, applied = (bool(mask & (1 << bit)) for mask in (requested_mask, proposed_mask, applied_mask))
        forced = proposed_mask | (1 << bit)
        constraints = []
        if not requested:
            constraints.append("not_requested")
        if not feeder_available.get(svc["feeder"], False):
            constraints.append("open_feeder")
        if sum(s["watts"] for i, s in enumerate(services) if forced & (1 << i)) > capacity_w:
            constraints.append("source_capacity")
        if sum(s["watts"] for i, s in enumerate(services) if s["feeder"] == svc["feeder"] and forced & (1 << i)) > feeder_limits.get(svc["feeder"], 0):
            constraints.append("feeder_capacity")
        if proposed and not applied:
            constraints.append("restoration_dwell_or_stability")
        _, contribution = score((1 << bit) if proposed else 0, services, activity, 0, policy, waiting_s)
        contribution["switching"] = -policy.switching_penalty * int(proposed != bool(previous_mask & (1 << bit)))
        reason = (f"Selected by {policy.name} under protected-first lexicographic objective" if applied else
                  "Selected but waiting for stable evidence and restoration dwell" if proposed else
                  "Not selected: " + ", ".join(constraints) if constraints else
                  "Not selected: lower lexicographic preference than winning plan")
        decisions.append(dict(service_id=svc["id"], requested=requested, proposed=proposed, applied=applied,
                              binding_constraints=constraints if not applied else [], reason=reason, score_terms=contribution,
                              shortfall_w=svc["watts"] if requested and not applied else 0,
                              counterfactual="served" if applied else "force-on violates " + ", ".join(constraints)
                              if constraints else "lower lexicographic preference than selected mask"))
    payload = dict(inputs=inputs, proposed_mask=proposed_mask, applied_mask=applied_mask)
    return dict(decision_id=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                policy=policy.model_dump(), objective_order=policy.objective_order,
                score_terms=terms, replay_inputs=inputs, decisions=decisions)


def fixed_priority_mask(services, capacity_w, feeder_limits, feeder_available, requested_mask):
    """Fixed-order reference allocation over the same demand and physical limits."""
    order = (0, 1, 2, 3, 4, 5)
    mask = 0
    for bit in order:
        candidate = mask | (1 << bit)
        if requested_mask & (1 << bit) and feasible(candidate, services, capacity_w, feeder_limits, feeder_available):
            mask = candidate
    return mask
