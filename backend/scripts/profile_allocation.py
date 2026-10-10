"""Exact-oracle latency at shipped six-service and experimental 19-leaf scales."""
import json
import statistics
import time
from pathlib import Path
from app.core.allocator import allocate
from app.core.state import SERVICE_CATALOG
from app.visualizers import LOADS

leaves = [dict(s) for s in SERVICE_CATALOG[:3]]
for cid, loads in LOADS.items():
    for key, _, watts, _ in loads:
        leaves.append(dict(id=f'{cid}:{key}', tier='T2', zone='classroom', classroom_id=cid, feeder='B', watts=watts))
activity = {cid: {'state': 'ACTIVE'} for cid in LOADS}
results = {}
for name, catalog, repeats in [('services6', SERVICE_CATALOG, 50), ('experimental_leaves19', leaves, 3)]:
    assert len(catalog) == (6 if name == 'services6' else 19)
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        mask = allocate(catalog, 10000, {'A': 6000, 'B': 8000}, {'A': True, 'B': True}, (1 << len(catalog))-1, activity)
        samples.append((time.perf_counter()-start)*1000)
    results[name] = dict(n=repeats, masks=1 << len(catalog), median_ms=statistics.median(samples), max_ms=max(samples), selected_mask=mask)
    print(name, results[name], flush=True)
results['decision'] = 'Keep exact 64-mask runtime. 19-leaf enumeration is offline only; do not expand the control catalog without a bounded solver and safety-equivalence tests.'
Path('backend/benchmarks/results/allocation_profile.json').write_text(json.dumps(results, indent=2)+'\n')
