from fastapi.testclient import TestClient
import app.main as main
from app.core.allocator import allocate, explain, feasible
from app.core.policy import AllocationPolicy
from app.core.state import SERVICE_CATALOG as C

LIMITS = {"A": 6000, "B": 8000}
AVAILABLE = {"A": True, "B": True}
ACTIVITY = {cid: {"state": "ACTIVE"} for cid in ("CR1", "CR2", "CR3")}


def test_policies_replay_and_explanations():
    masks = []
    for name in ("activity_first", "water_first"):
        policy = AllocationPolicy(name=name)
        mask = allocate(C, 6000, LIMITS, AVAILABLE, 63, ACTIVITY, policy=policy)
        masks.append(mask)
        assert mask & 3 == 3
        assert feasible(mask, C, 6000, LIMITS, AVAILABLE)
        result = explain(C, 6000, LIMITS, AVAILABLE, 63, ACTIVITY, 0, policy, {}, mask, mask)
        inp = result['replay_inputs'].copy()
        inp['policy'] = AllocationPolicy(**inp['policy'])
        assert allocate(**inp) == mask
        assert len(result['decisions']) == 6
        assert all(d['counterfactual'] and d['reason'] and d['score_terms'] for d in result['decisions'])
    assert masks[0] != masks[1]


def test_hard_constraints_and_determinism():
    for name in ("activity_first", "water_first"):
        for cap in range(0, 15000, 500):
            p = AllocationPolicy(name=name, fairness_weight=100, switching_penalty=100)
            m = allocate(C, cap, LIMITS, {"A": True, "B": False}, 63, ACTIVITY, policy=p, waiting_s={"L5": 3600})
            assert feasible(m, C, cap, LIMITS, {"A": True, "B": False})
            assert not m & 56
            if cap >= 3000:
                assert m & 3 == 3
            assert m == allocate(C, cap, LIMITS, {"A": True, "B": False}, 63, ACTIVITY, policy=p, waiting_s={"L5": 3600})


def test_fairness_breaks_optional_tie():
    p = AllocationPolicy(fairness_weight=1)
    first = allocate(C, 5000, LIMITS, AVAILABLE, 63, ACTIVITY, policy=p)
    next_mask = allocate(C, 5000, LIMITS, AVAILABLE, 63, ACTIVITY, first, p, {"L4": 10})
    assert first & 8 and next_mask & 16
    assert next_mask & 3 == 3


def test_policy_api_validation_and_restoration():
    with TestClient(main.app) as client:
        before = main.grid.last_allocation_mask
        r = client.put('/api/v1/allocation/policy', json={"name": "water_first", "fairness_weight": 1})
        assert r.status_code == 200
        assert main.grid.last_allocation_mask & ~before == 0
        snapshot = client.get('/api/v1/snapshot').json()
        assert snapshot['allocation']['explanation']['policy']['name'] == 'water_first'
        assert client.put('/api/v1/allocation/policy', json={"name": "unsafe"}).status_code == 422
        assert client.put('/api/v1/allocation/policy', json={"fairness_weight": True}).status_code == 422
        assert client.put('/api/v1/allocation/policy', json={"protected": []}).status_code == 422


def test_applied_decision_restoration_replay():
    from app.core.restoration import RestorationGate
    with TestClient(main.app) as client:
        client.post('/api/v1/simulation/capacity', json={'capacity_w': 5000})
        payload = client.get('/api/v1/snapshot').json()
        explanation = payload['allocation']['explanation']
        replay = explanation['restoration_replay']
        gate = RestorationGate(lambda: replay['now_s'])
        vars(gate).update(replay['before'])
        assert gate.update(payload['proposed_mask'], replay['signature'], replay['order'], now=replay['now_s']) == payload['modeled_mask']
        assert sum(d['shortfall_w'] for d in explanation['decisions']) == sum(s['watts'] for s in payload['services'] if s['requested'] and not s['modeled_served'])


def test_waiting_age_only_accumulates_for_unserved_requests():
    grid = main.grid
    now = [0.]
    grid.clock = lambda: now[0]
    grid.last_policy_tick = 0
    grid.software_mode = True
    grid.source_capacity_w = 3000
    grid.policy = AllocationPolicy(fairness_weight=1)
    grid.control_revision += 1
    grid.tick()
    now[0] = 10.
    grid.tick()
    assert grid.waiting_s['L3'] == 0  # No classroom request: no artificial starvation credit.
    assert grid.waiting_s['L2'] == 10


def test_explanation_inputs_do_not_follow_live_mutation():
    available = dict(AVAILABLE)
    result = explain(C, 6000, LIMITS, available, 63, ACTIVITY, 0, AllocationPolicy(), {}, 7, 7)
    available['A'] = False
    assert result['replay_inputs']['feeder_available']['A'] is True


def test_idle_tick_preserves_the_decision_trace():
    now = [100.]
    grid = main.grid
    grid.clock = lambda: now[0]
    grid.tick()
    before = grid.build_snapshot().allocation.explanation
    now[0] += .25
    grid.tick()
    assert grid.build_snapshot().allocation.explanation == before
