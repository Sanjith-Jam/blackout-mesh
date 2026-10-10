from fastapi.testclient import TestClient
import app.main as main


def test_combined_and_stuck_examples_return_evidence_without_mutating_site():
    client = TestClient(main.app)
    before = main.app.state.site.revision
    data = client.post('/api/v1/visualizers/hospital', json={'scenario': 'overload_cooling'}).json()
    codes = {h['code'] for h in data['transformers'][1]['diagnosis']['hypotheses']}
    assert {'OVERLOAD', 'COOLING_FAILURE'} <= codes
    data = client.post('/api/v1/visualizers/hospital', json={'scenario': 'stuck_sensor'}).json()
    diagnosis = data['transformers'][1]['diagnosis']
    assert diagnosis['status'] == 'ABSTAINED'
    assert diagnosis['abstention']['next_check_needed']
    assert main.app.state.site.revision == before
