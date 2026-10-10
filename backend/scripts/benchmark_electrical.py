"""Matched end-to-end reference studies, including build/validation and serial batch latency."""
import json
import platform
import statistics
import time
from pathlib import Path
from app.simulation.electrical import ElectricalInput, solve

CASES = {'normal': {}, 'overload': {'load_a_w': 12000, 'load_b_w': 16000},
         'open_branch': {'feeder_b_closed': False}, 'upstream_loss': {'source_on': False},
         'nonconvergence': {'resistance_ohm': 10., 'load_a_w': 100000, 'load_b_w': 100000}}


def latency(fn, repeats=20):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter(); fn(); samples.append((time.perf_counter()-start)*1000)
    samples.sort()
    return {'n': repeats, 'p50_ms': statistics.median(samples), 'p95_ms': samples[int(.95*(repeats-1))]}


def main():
    results = {}
    for engine in ('power-grid-model', 'pandapower'):
        start = time.perf_counter(); first = solve(ElectricalInput(), engine)
        first_ms = (time.perf_counter()-start)*1000
        assert first.converged, first.reason
        cases = {name: solve(ElectricalInput(**values), engine).model_dump() for name, values in CASES.items()}
        results[engine] = {'first_import_build_solve_ms': first_ms, 'cases': cases,
            'single': latency(lambda: solve(ElectricalInput(), engine)),
            'serial_batch16': latency(lambda: [solve(ElectricalInput(), engine) for _ in range(16)], 5)}
    comparisons = {}
    for name in ('normal', 'overload', 'open_branch'):
        a, b = (results[e]['cases'][name] for e in ('power-grid-model', 'pandapower'))
        assert a['converged'] and b['converged']
        dv = max(abs(a['buses'][bus]['voltage_v']-b['buses'][bus]['voltage_v']) for bus in a['buses'] if a['buses'][bus]['energized'])
        di = max(abs(a['branches'][branch]['current_a']-b['branches'][branch]['current_a']) for branch in a['branches'] if a['branches'][branch]['energized'])
        dp = abs(a['source_p_w']-b['source_p_w'])
        assert dv < .01 and di < .001 and dp < .1
        comparisons[name] = dict(max_voltage_difference_v=dv, max_current_difference_a=di, source_power_difference_w=dp)
    output = {'environment': platform.platform(), 'python': platform.python_version(), 'engines': results,
              'tolerances': {'voltage_v': .01, 'current_a': .001, 'power_w': .1}, 'comparisons': comparisons,
              'selected_runtime': 'power-grid-model', 'batch_method': '16 serial adapter calls, including graph/build/validation; not native vectorized batch'}
    path = Path(__file__).resolve().parents[1]/'benchmarks/results/electrical_report.json'
    path.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({e: {key: v for key, v in value.items() if key != 'cases'} for e, value in results.items()}, indent=2))

if __name__ == '__main__':
    main()
