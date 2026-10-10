"""Regression checks for the merged application and transport lifecycle."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import create_app
from app.storage.models import Acknowledgment, Decision, Incident, Run


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


def test_database_degradation_is_visible_in_health():
    application = create_app()
    with TestClient(application) as client:
        application.state.grid.storage.degraded = True
        application.state.grid.storage.degraded_reason = 'test failure'
        health = client.get('/api/v1/health').json()
        assert health['status'] == 'degraded'
        assert health['storage'] == {'status': 'DEGRADED', 'degraded_reason': 'test failure'}


def test_audit_failure_rejects_command_before_state_changes():
    application = create_app()
    with TestClient(application) as client:
        grid = application.state.grid
        original_capacity = grid.source_capacity_w
        grid.storage.degraded = True
        response = client.post('/api/v1/simulation/capacity', json={'capacity_w': 4000})
        assert response.status_code == 503
        assert grid.source_capacity_w == original_capacity


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
        application.state.grid._sync_incidents([{"code": "TEST_FAULT", "asset_id": "TX1", "severity": "low"}])
        with Session(application.state.grid.storage.engine) as session:
            incident_id = session.exec(select(Incident)).one().incident_id
    restarted = create_app()
    with TestClient(restarted):
        with Session(restarted.state.grid.storage.engine) as session:
            assert session.exec(select(Run).where(Run.run_id == run_id)).first()
            assert session.exec(select(Decision).where(Decision.run_id == run_id)).first()
            assert len(session.exec(select(Acknowledgment).where(Acknowledgment.run_id == run_id)).all()) == 1
            assert session.exec(select(Incident).where(Incident.incident_id == incident_id)).one().status == "OPEN"


def test_duplicate_ack_is_idempotent_and_both_sqlite_stores_can_be_backed_up(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "audit.db"}')
    monkeypatch.setenv('PRIORITYGRID_HISTORY_DB', str(tmp_path / 'history.db'))
    application = create_app()
    with TestClient(application) as client:
        grid = application.state.grid
        ack = {'device_boot': 'demo', 'sequence': 9, 'session': 'run',
               'confirmed_mask': 3, 'provenance': 'SIMULATED'}
        before = grid.control_revision
        assert client.post('/api/v1/hardware/ack', json=ack).status_code == 200
        after_first = grid.control_revision
        assert after_first > before
        assert client.post('/api/v1/hardware/ack', json=ack).status_code == 200
        assert grid.control_revision == after_first
        with Session(grid.storage.engine) as session:
            assert len(session.exec(select(Acknowledgment).where(Acknowledgment.run_id == grid.run_id)).all()) == 1
        db_backup = grid.storage.backup(tmp_path / 'audit-backup.db')
        history_backup = grid.history.store.backup(tmp_path / 'history-backup.db')
        for backup, table in ((db_backup, 'acknowledgment'), (history_backup, 'historyrecord')):
            with sqlite3.connect(backup) as connection:
                assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] > 0
        with sqlite3.connect(db_backup) as connection:
            assert connection.execute('SELECT MAX(version) FROM schema_migration').fetchone()[0] == 1
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO command(command_id, run_id, revision, timestamp, action, payload) VALUES ('orphan', 'missing-run', 0, 'now', 'test', '{}')")
        from app.storage.db import Storage
        restored = Storage(f'sqlite:///{db_backup}')
        restored.init()
        with Session(restored.engine) as session:
            assert session.exec(select(Acknowledgment)).first()
        restored.engine.dispose()
        restored_history = application.state.grid.history.store.__class__(history_backup)
        assert restored_history.runs('campus')
        restored_history.engine.dispose()
