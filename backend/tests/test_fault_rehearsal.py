from fastapi.testclient import TestClient
import app.main as main


def test_combined_and_stuck_examples_return_evidence_without_mutating_site():
    client = TestClient(main.app)
    before = main.app.state.site.revision
    data = client.post('/api/v1/visualizers/hospital', json={'rehearsal': 'overload_cooling'}).json()
    codes = {h['code'] for h in data['transformers'][1]['diagnosis']['hypotheses']}
    assert {'OVERLOAD', 'COOLING_FAILURE'} <= codes
    data = client.post('/api/v1/visualizers/hospital', json={'rehearsal': 'stuck_sensor'}).json()
    diagnosis = data['transformers'][1]['diagnosis']
    assert diagnosis['status'] == 'ABSTAINED'
    assert diagnosis['abstention']['next_check_needed']
    assert main.app.state.site.revision == before


def test_rehearsals_cannot_be_combined_with_live_controls():
    client = TestClient(main.app)
    before = main.app.state.site.revision
    for extra in ({'action': 'clear_fault'}, {'fault': 'overload'}, {'scenario': 'overload'},
                  {'zone_id': 'ICU'}, {'capacity_w': 6000}):
        assert client.post('/api/v1/visualizers/hospital', json={'rehearsal': 'normal', **extra}).status_code == 422
    assert main.app.state.site.revision == before
