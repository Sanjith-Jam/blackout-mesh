import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.api.demo import CityDemoResponse, evidence
from app.core.allocator import fixed_priority_mask
from app.core.state import SERVICE_CATALOG


def test_city_projection_same_revision_and_no_read_mutation():
    client = TestClient(main.app)
    site = main.app.state.site
    before = (site.revision, site.grid.tick_count, list(main.app.state.demand_forecast.samples))
    for _ in range(3):
        response = client.get('/api/v1/demo?source=SYNTHETIC_REPLAY')
        assert response.status_code == 200
        data = response.json()
        CityDemoResponse.model_validate(data)
        assert data['snapshot']['site']['revision'] == data['snapshot']['contract']['identity']['state_revision']
        assert data['forecast']['capacity_w'] == data['snapshot']['source']['capacity_w']
        assert data['hardware']['confirmed_mask'] is None
    assert before == (site.revision, site.grid.tick_count, list(main.app.state.demand_forecast.samples))


def test_shortage_forecast_and_feeder_trip_stay_separate_from_control():
    client = TestClient(main.app)
    client.post('/api/v1/simulation/capacity', json={'capacity_w': 6000}).raise_for_status()
    data = client.get('/api/v1/demo?source=SYNTHETIC_REPLAY').json()
    assert data['forecast']['status'] == 'SHORTAGE_RISK'
    snapshot = data['snapshot']
    expected = fixed_priority_mask(SERVICE_CATALOG, 6000, snapshot['feeder_limits_w'], {'A': True, 'B': True}, snapshot['requested_mask'])
    assert snapshot['allocation']['baseline_mask'] == expected
    client.post('/api/v1/simulation/feeder', json={'feeder': 'A', 'available': False}).raise_for_status()
    snapshot = client.get('/api/v1/demo').json()['snapshot']
    assert not any(s['modeled_served'] for s in snapshot['services'] if s['feeder'] == 'A')
    assert snapshot['allocation']['critical_shortfall_w'] > 0


def test_forecast_records_requested_not_post_shedding_demand():
    state = main.app.state
    state.grid.set_capacity(0)
    state.control_loop.tick_once()
    snapshot = state.grid.build_snapshot()
    assert snapshot.allocation.served_w == 0
    assert state.demand_forecast.samples[-1] == sum(s.watts for s in snapshot.services if s.requested)
    assert state.demand_forecast.samples[-1] > 0


def test_invalid_forecast_requests_and_benchmark_provenance():
    client = TestClient(main.app)
    for query in ['source=truth', 'replay_index=-1', 'replay_index=8', 'replay_index=NaN', 'replay_index=1.5']:
        assert client.get('/api/v1/demo?' + query).status_code == 422
    result = client.get('/api/v1/demo/evidence').json()
    backend = Path(__file__).resolve().parents[1]
    allocation = json.loads((backend / 'benchmarks/results/allocation_report.json').read_text())
    assert result['allocation_runs'] == len(allocation['runs'])
    assert result['constraint_violations'] == sum(r['constraint_violations'] for r in allocation['runs'])
    assert result['inference_median_ms'] == evidence().inference_median_ms
    assert result['forecast_mae_60s_w'] < result['persistence_mae_60s_w']


def test_hardware_reads_do_not_hold_the_site_lock(monkeypatch):
    from types import SimpleNamespace
    class Bridge:
        def status(self):
            assert not main.app.state.site._lock._is_owned()
            return {'link': 'NOT_CONFIGURED', 'commanded_mask': None, 'confirmed_mask': None}
    monkeypatch.setattr(main.app.state, 'gateway', (Bridge(), SimpleNamespace(error=None)))
    assert TestClient(main.app).get('/api/v1/demo').status_code == 200
