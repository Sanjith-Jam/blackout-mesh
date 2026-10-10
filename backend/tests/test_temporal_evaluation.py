import csv
import io
import json
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_temporal as audit


def archive(conflict=False):
    buf = io.BytesIO()
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(['date', 'Temperature', 'Humidity', 'Light', 'CO2', 'HumidityRatio', 'Occupancy'])
    for day in range(12):
        for sample in range(4):
            ts = datetime(2015, 2, 2) + timedelta(days=day, minutes=sample)
            writer.writerow([sample, ts.strftime('%Y-%m-%d %H:%M:%S'), day+20, 30+sample,
                             sample*100, 400+sample*300, .004, sample % 2])
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('datatraining.txt', text.getvalue())
        z.writestr('datatest.txt', text.getvalue().replace('20,30,0,400', '99,30,0,400') if conflict else text.getvalue())
        z.writestr('datatest2.txt', text.getvalue())
    return buf.getvalue()


def test_disjoint_days_and_scaler_fit_training_only(monkeypatch):
    fitted = []
    original = audit.StandardScaler.fit
    def fit(self, X, y=None, **kwargs):
        fitted.append(X.copy())
        return original(self, X, y, **kwargs)
    monkeypatch.setattr(audit.StandardScaler, 'fit', fit)
    result = audit.run(archive())
    assert result['adopted'] is False and result['duplicates_removed'] == 96
    for i, fold in enumerate(result['folds']):
        tr, va, te = (fold['split'][key]['days'] for key in ('train', 'validation', 'evaluation'))
        assert max(tr) < min(va) and max(va) < min(te)
        for training_data in fitted[i*2:i*2+2]:
            assert len(training_data) == fold['split']['train']['n']
            assert training_data[:, 0].max() == 20+len(tr)-1
    assert result['features'] == ['temperature_c', 'humidity_pct', 'co2_ppm', 'humidity_ratio']


def test_conflicts_and_gate_abstention():
    with pytest.raises(ValueError, match='conflicting'):
        audit.run(archive(True))
    # A candidate that confidently calls every occupied row inactive cannot pass the gate.
    assert audit.operating_point(np.array([[1., 0.], [1., 0.]]), np.array([1, 1])) is None
    m = audit.report_metrics(np.array([0, 1]), np.array([-1, -1]))
    assert m['coverage'] == 0 and m['selective_risk'] is None
    results = json.loads((audit.OUT/'results.json').read_text())
    assert results['baseline_artifact_sha256_unchanged'] == 'b552641e908e6c1011c61223401f6e527d9d87aebc247025cf4812c1243efdf9'
