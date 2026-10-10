"""Regression checks for the merged application and transport lifecycle."""
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import create_app
from app.storage.models import Acknowledgment, Decision, Run


def test_apps_own_independent_state_and_stop_their_loops():
    first, second = create_app(), create_app()
    with TestClient(first) as a, TestClient(second) as b:
        assert first.state.grid is not second.state.grid
        assert first.state.site.run_id != second.state.site.run_id
        assert a.post('/api/v1/simulation/capacity', json={'capacity_w': 4000}).status_code == 200
        assert b.get('/api/v1/snapshot').json()['source']['capacity_w'] == 14000
        assert first.state.grid.source_capacity_w == 4000
        for route in ('/api/v1/snapshot', '/api/v1/visualizers/classrooms',
                      '/api/v1/visualizers/hospital', '/api/v1/health'):
            assert a.get(route).status_code == 200
        with a.websocket_connect('/ws/live') as socket:
            message = socket.receive_json()
            assert message['type'] == 'snapshot'
            assert message['payload']['contract']['identity']['run_id'] == first.state.site.run_id
            assert message['sent_at']
    assert first.state.control_loop.task is None
    assert second.state.control_loop.task is None


def test_sqlite_audit_survives_restart_without_confirming_physical_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "audit.db"}')
    application = create_app()
    with TestClient(application) as client:
        run_id = application.state.grid.run_id
        assert client.post('/api/v1/simulation/capacity', json={'capacity_w': 4000}).status_code == 200
        ack = {'device_boot': 'demo', 'sequence': 1, 'session': 'demo',
               'confirmed_mask': 0, 'provenance': 'SIMULATED'}
        assert client.post('/api/v1/hardware/ack', json=ack).status_code == 200
        assert client.post('/api/v1/hardware/ack', json={**ack, 'provenance': 'PHYSICAL'}).status_code == 422
        assert client.get('/api/v1/snapshot').json()['indicator_confirmed_mask'] is None
    restarted = create_app()
    with TestClient(restarted):
        with Session(restarted.state.grid.storage.engine) as session:
            assert session.exec(select(Run).where(Run.run_id == run_id)).first()
            assert session.exec(select(Decision).where(Decision.run_id == run_id)).first()
            assert len(session.exec(select(Acknowledgment).where(Acknowledgment.run_id == run_id)).all()) == 1
