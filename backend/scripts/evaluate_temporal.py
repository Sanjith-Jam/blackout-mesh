#!/usr/bin/env python3
"""Exploratory rolling-origin audit; never writes shipped model files."""
import argparse
import csv
import hashlib
import io
import json
import platform
import resource
import time
import zipfile
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from train_activity import FEATURES, rows_from_zip, metrics, latency_ms, apply_operating_point

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'backend/benchmarks/occupancy'


def splits(rows):
    days = sorted({r[0].date().isoformat() for r in rows})
    return [(days[:end], days[end:end+2], days[end+2:end+4]) for end in range(6, len(days)-3, 2)]


def operating_point(prob, y):
    choices = []
    for threshold in (.15, .24, .35, .5):
        for margin in (0, .05, .15):
            point = dict(decision_threshold=threshold, abstain_margin=margin)
            result = metrics(y, apply_operating_point(prob, point))
            rate = result['false_inactive_rate_of_occupied']
            if result['coverage'] >= .9 and rate is not None and rate <= .05:
                choices.append(((result['macro_f1_all_rows_unknown_as_error'], result['coverage'], -rate), point))
    return max(choices, key=lambda x: x[0])[1] if choices else None


def report_metrics(y, pred):
    result = metrics(y, pred)
    result['selective_risk'] = None if result['accuracy_covered'] is None else 1-result['accuracy_covered']
    return result


def run(raw):
    rows = rows_from_zip(raw)
    timestamps = [r[0] for r in rows]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError('conflicting records at one timestamp')
    light = {}
    source_rows = 0
    for name in ('datatraining.txt', 'datatest.txt', 'datatest2.txt'):
        for row in csv.reader(io.StringIO(zipfile.ZipFile(io.BytesIO(raw)).read(name).decode('utf-8-sig'))):
            if row and row[0] != 'date':
                source_rows += 1
                key = row[1]
                if key in light and light[key] != float(row[4]):
                    raise ValueError('conflicting Light observation')
                light[key] = float(row[4])
    X = np.array([r[1] for r in rows]); y = np.array([r[2] for r in rows])
    Xlight = np.column_stack((X, [light[r[0].strftime('%Y-%m-%d %H:%M:%S')] for r in rows]))
    dates = np.array([r[0].date().isoformat() for r in rows])
    artifact = ROOT / 'backend/models/activity-logistic.joblib'
    before = hashlib.sha256(artifact.read_bytes()).hexdigest()
    folds, pooled = [], {}
    for train_days, val_days, test_days in splits(rows):
        assert set(train_days).isdisjoint(val_days) and set(val_days).isdisjoint(test_days) and set(train_days).isdisjoint(test_days)
        ix = [np.flatnonzero(np.isin(dates, d)) for d in (train_days, val_days, test_days)]
        tr, va, te = ix
        models = {'logistic': make_pipeline(StandardScaler(), LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)),
                  'tree': DecisionTreeClassifier(max_depth=6, min_samples_leaf=20, class_weight='balanced', random_state=42),
                  'logistic_light_experiment': make_pipeline(StandardScaler(), LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42))}
        fold = {'split': {key: {'days': d, 'n': len(i), 'row_ids_sha256': hashlib.sha256(','.join(map(str, i)).encode()).hexdigest()}
                         for key, d, i in zip(('train', 'validation', 'evaluation'), (train_days, val_days, test_days), ix)}, 'models': {},
                'train_feature_mean': X[tr].mean(axis=0).tolist(), 'evaluation_feature_mean': X[te].mean(axis=0).tolist()}
        predictions = {'majority': np.full(len(te), np.bincount(y[tr], minlength=2).argmax()), 'co2_rule': (X[te, 2] >= 1000).astype(int)}
        for name, model in models.items():
            data = Xlight if 'light' in name else X
            model.fit(data[tr], y[tr])
            point = operating_point(model.predict_proba(data[va]), y[va])
            predictions[name] = apply_operating_point(model.predict_proba(data[te]), point) if point else np.full(len(te), -1)
            buf = io.BytesIO(); joblib.dump(model, buf)
            fold['models'][name] = {'operating_point': point, 'validation_gate_passed': point is not None,
                'ungated_threshold_0_5_exploratory': report_metrics(y[te], model.predict(data[te])),
                'artifact_bytes': len(buf.getvalue()), 'single_latency': latency_ms(lambda: model.predict_proba(data[te[:1]]), 30),
                'batch128_latency': latency_ms(lambda: model.predict_proba(data[te[:128]]), 30)}
        for name, pred in predictions.items():
            fold['models'].setdefault(name, {}).update(metrics=report_metrics(y[te], pred),
                per_day={d: report_metrics(y[te][dates[te] == d], pred[dates[te] == d]) for d in test_days})
            pooled.setdefault(name, []).append((y[te], pred))
        folds.append(fold)
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == before
    return {'status': 'EXPLORATORY_ONLY; campus generalization unvalidated', 'adopted': False,
            'dataset_sha256': hashlib.sha256(raw).hexdigest(), 'protocol_sha256': hashlib.sha256((OUT/'PROTOCOL.md').read_bytes()).hexdigest(),
            'baseline_artifact_sha256_unchanged': before, 'features': FEATURES, 'light_experiment_features': FEATURES + ['Light'],
            'source_rows': source_rows, 'deduplicated_rows': len(rows), 'duplicates_removed': source_rows-len(rows),
            'excluded_tail_days': sorted(set(dates)-set(d for fold in folds for part in fold['split'].values() for d in part['days'])),
            'folds': folds, 'pooled': {n: report_metrics(np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])) for n, parts in pooled.items()},
            'environment': {'python': platform.python_version(), 'sklearn': sklearn.__version__, 'numpy': np.__version__, 'platform': platform.platform(),
                            'peak_process_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--data', required=True)
    args = parser.parse_args()
    result = run(Path(args.data).read_bytes())
    (OUT/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['pooled'], indent=2))
