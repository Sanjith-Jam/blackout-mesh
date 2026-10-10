import asyncio
from importlib.util import find_spec

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main
from starlette.requests import Request
from app.simulation.electrical import ElectricalInput, solve, telemetry, diagnose_study


@pytest.mark.parametrize('bad', [{'loads_w': {'A': True}}, {'loads_w': {'B': -1}}, {'resistance_ohm': 0.},
                                  {'reactance_ohm': -1.}, {'power_factor': float('nan')}, {'balanced': False}, {'balanced': 1}, {'truth': 'overload'}])
def test_invalid_parameters(bad):
    with pytest.raises(ValidationError):
        ElectricalInput(**bad)


def test_failed_engine_never_fabricates_observations():
    result = solve(ElectricalInput(), 'invalid')
    assert result.status == 'failed' and not result.restoration_authorized
    assert result.source_p_w is None
    assert all(o.value is None for o in telemetry(result, 1))
    assert diagnose_study(result)['status'] == 'ABSTAINED'


@pytest.mark.skipif(find_spec('power_grid_model') is None, reason='optional electrical environment required')
def test_reference_conservation_islands_and_failure():
    normal = solve(ElectricalInput())
    assert normal.converged, normal.reason
    assert normal.source_p_w == pytest.approx(14000 + normal.loss_w, abs=.1)
    assert normal.loss_w > 0
    assert abs(normal.power_balance_residual_w) < .1
    assert normal.loss_w == pytest.approx(sum(3 * b["current_a"]**2 * .04 for b in normal.branches.values()))
    for branch in normal.branches.values():
        assert branch['current_a'] > 0 and branch['loading_pct'] < 100
        # Three-phase source-terminal apparent power agrees with RMS current.
        assert (branch['p_w']**2 + branch['q_var']**2)**.5 == pytest.approx(3**.5 * 400 * branch['current_a'], rel=1e-6)
    overload = solve(ElectricalInput(loads_w={'A': 12000, 'B': 8000}))
    assert overload.branches['A']['loading_pct'] > 100
    assert diagnose_study(overload)['current_alarms'] == ['A']
    opened = solve(ElectricalInput(feeders_closed={'A': True, 'B': False}))
    assert opened.converged and opened.buses['B']['voltage_v'] is None
    assert opened.branches['B']['p_w'] is None
    assert opened.source_p_w == pytest.approx(6000 + opened.loss_w, abs=.1)
    off = solve(ElectricalInput(source_on=False))
    assert off.status == 'deenergized' and not off.converged
    failed = solve(ElectricalInput(), max_iterations=0)
    assert failed.status == 'failed' and all(o.value is None for o in telemetry(failed, 1))
    assert not failed.restoration_authorized


def test_study_api_and_stale_revision(monkeypatch):
    def fake(inputs):
        return solve(inputs, 'invalid')
    monkeypatch.setattr(main, 'solve_electrical', fake)
    with TestClient(main.app) as client:
        before = main.app.state.grid.last_allocation_mask
        result = client.post('/api/v1/studies/electrical', json={})
        assert result.status_code == 200
        assert result.json()['result']['restoration_authorized'] is False
        assert main.app.state.grid.last_allocation_mask == before
        assert client.post('/api/v1/studies/electrical', json={'loads_w': {'A': '6000'}}).status_code == 422
    def stale(inputs):
        main.app.state.site.new_run()
        return fake(inputs)
    monkeypatch.setattr(main, 'solve_electrical', stale)
    with TestClient(main.app) as client:
        assert client.post('/api/v1/studies/electrical', json={}).status_code == 409


def test_slow_study_does_not_block_event_loop(monkeypatch):
    import time
    def slow(inputs):
        time.sleep(.1)
        return solve(inputs, 'invalid')
    monkeypatch.setattr(main, 'solve_electrical', slow)
    async def run():
        main.app.state.electrical_study_lock = asyncio.Lock()
        pending = asyncio.create_task(main.electrical_study(Request({"type": "http", "app": main.app}), ElectricalInput()))
        await asyncio.sleep(.02)
        assert not pending.done()
        with pytest.raises(HTTPException) as busy:
            await main.electrical_study(Request({"type": "http", "app": main.app}), ElectricalInput())
        assert busy.value.status_code == 503
        await pending
    asyncio.run(run())


def test_timeout_keeps_worker_slot_and_never_applies_result(monkeypatch):
    import time
    def slow(inputs):
        time.sleep(.08)
        return solve(inputs, 'invalid')
    monkeypatch.setattr(main, 'solve_electrical', slow)
    monkeypatch.setattr(main, 'ELECTRICAL_TIMEOUT_S', .01)
    async def run():
        main.app.state.electrical_study_lock = asyncio.Lock()
        before = main.app.state.grid.last_allocation_mask
        with pytest.raises(HTTPException) as timeout:
            await main.electrical_study(Request({"type": "http", "app": main.app}), ElectricalInput())
        assert timeout.value.status_code == 504
        assert main.app.state.electrical_study_lock.locked()
        with pytest.raises(HTTPException) as busy:
            await main.electrical_study(Request({"type": "http", "app": main.app}), ElectricalInput())
        assert busy.value.status_code == 503
        await asyncio.sleep(.1)
        assert not main.app.state.electrical_study_lock.locked()
        assert main.app.state.grid.last_allocation_mask == before
    asyncio.run(run())


@pytest.mark.skipif(find_spec('power_grid_model') is None, reason='optional electrical environment required')
def test_real_engine_through_api():
    solve(ElectricalInput())  # Warm optional imports before a revision-sensitive request.
    with TestClient(main.app) as client:
        response = client.post('/api/v1/studies/electrical', json={})
        assert response.status_code == 200, response.text
        result = response.json()['result']
        assert result['engine'] == 'power-grid-model' and result['converged']
        assert result['restoration_authorized'] is False
        assert abs(result['power_balance_residual_w']) < .1
        assert client.get('/api/v1/snapshot').json()['source']['model'] == 'watt_budget'


def test_simultaneous_requests_cannot_queue_a_second_worker(monkeypatch):
    import time
    def slow(inputs):
        time.sleep(.05)
        return solve(inputs, 'invalid')
    monkeypatch.setattr(main, 'solve_electrical', slow)
    async def run():
        main.app.state.electrical_study_lock = asyncio.Lock()
        results = await asyncio.gather(main.electrical_study(Request({"type": "http", "app": main.app}), ElectricalInput()),
                                       main.electrical_study(Request({"type": "http", "app": main.app}), ElectricalInput()), return_exceptions=True)
        assert sum(isinstance(r, dict) for r in results) == 1
        errors = [r for r in results if isinstance(r, HTTPException)]
        assert len(errors) == 1 and errors[0].status_code == 503
    asyncio.run(run())


def test_missing_optional_engine_returns_unavailable(monkeypatch):
    from importlib.metadata import PackageNotFoundError
    import app.simulation.electrical as electrical
    def missing(_):
        raise PackageNotFoundError('power-grid-model')
    monkeypatch.setattr(electrical, 'version', missing)
    result = electrical.solve(ElectricalInput())
    assert result.status == 'unavailable'
    assert result.source_p_w is None and not result.restoration_authorized
    assert diagnose_study(result)['status'] == 'ABSTAINED'
