"""Optional balanced AC studies. No control mutations, thermal model or hardware claims."""
import math
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Literal, Dict, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

TOPOLOGY_VERSION = 'radial-400v-v1'
NOMINAL_V = 400.0

class ElectricalInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    topology_version: Literal['radial-400v-v1'] = TOPOLOGY_VERSION
    balanced: StrictBool = True
    source_on: StrictBool = True
    power_factor: float = Field(default=.95, ge=.8, le=1, allow_inf_nan=False)
    resistance_ohm: float = Field(default=.04, gt=0, le=10, allow_inf_nan=False)
    reactance_ohm: float = Field(default=.015, ge=0, le=10, allow_inf_nan=False)
    
    loads_w: Dict[str, StrictInt] = Field(default_factory=lambda: {'A': 6000, 'B': 8000})
    feeders_closed: Dict[str, StrictBool] = Field(default_factory=lambda: {'A': True, 'B': True})
    feeder_ratings_a: Dict[str, float] = Field(default_factory=lambda: {'A': 10.0, 'B': 14.0})

    @field_validator('balanced')
    @classmethod
    def require_balanced(cls, value):
        if not value:
            raise ValueError('only balanced three-phase studies are supported')
        return value

def reachability(inputs: ElectricalInput) -> set[str]:
    return {name for name, closed in inputs.feeders_closed.items() if closed and inputs.source_on}

class ElectricalResult(BaseModel):
    engine: str
    engine_version: Optional[str] = None
    status: Literal['converged', 'deenergized', 'failed', 'unavailable']
    converged: bool
    reason: Optional[str] = None
    observed_at: str
    inputs: ElectricalInput
    units: dict
    buses: dict
    branches: dict
    source_p_w: Optional[float] = None
    source_q_var: Optional[float] = None
    loss_w: Optional[float] = None
    power_balance_residual_w: Optional[float] = None
    provenance: Literal['ELECTRICAL_STUDY'] = 'ELECTRICAL_STUDY'

    @property
    def restoration_authorized(self) -> bool:
        return (self.converged and 
                all(b['loading_pct'] is not None and b['loading_pct'] < 100.0 for b in self.branches.values()) and
                self.source_p_w is not None and self.source_p_w > 0)

def solve(inputs: ElectricalInput, engine='power-grid-model', max_iterations=30):
    """One immutable study; missing/failed/islanded values stay null, never fabricated."""
    buses_init = {'source': {'energized': False, 'voltage_v': None}}
    for name in inputs.feeders_closed:
        buses_init[name] = {'energized': False, 'voltage_v': None}
    
    branches_init = {}
    for name in inputs.feeders_closed:
        branches_init[name] = {'energized': False, 'current_a': None, 'p_w': None, 'q_var': None, 'loading_pct': None}

    result = ElectricalResult(engine=engine, status='failed', converged=False,
        observed_at=datetime.now(timezone.utc).isoformat(), inputs=inputs,
        units={'voltage_v': 'V line-to-line RMS', 'current_a': 'A RMS', 'p_w': 'W total three-phase',
               'q_var': 'var total three-phase', 'loading_pct': '% ampacity', 'loss_w': 'W'},
        buses=buses_init,
        branches=branches_init)
    try:
        if engine not in ('power-grid-model', 'pandapower'):
            raise ValueError('unsupported electrical engine')
        result.engine_version = version(engine)
        reached = reachability(inputs)
        if not reached:
            result.status = 'deenergized'
            result.reason = 'No connected source; no AC solution or restoration permission'
            return result
        if engine == 'pandapower':
            buses, branches, p, q = _pandapower(inputs, reached, max_iterations)
        else:
            buses, branches, p, q = _pgm(inputs, reached, max_iterations)
        for name, voltage in buses.items():
            result.buses[name] = {'energized': True, 'voltage_v': voltage}
        for name, values in branches.items():
            result.branches[name] = {'energized': True, **values}
        numbers = list(buses.values()) + [v for values in branches.values() for v in values.values()] + [p, q]
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError('solver returned non-finite observations')
        served = sum(inputs.loads_w.get(name, 0) for name in reached)
        result.source_p_w, result.source_q_var = p, q
        result.loss_w = sum(3 * values['current_a']**2 * inputs.resistance_ohm for values in branches.values())
        result.power_balance_residual_w = p-served-result.loss_w
        if abs(result.power_balance_residual_w) > .1:
            raise ValueError('power-balance residual exceeds 0.1 W tolerance')
        result.status, result.converged = 'converged', True
        return result
    except Exception as exc:
        result.status = 'unavailable' if isinstance(exc, (ImportError, ModuleNotFoundError)) or type(exc).__name__ == 'PackageNotFoundError' else 'failed'
        result.reason = f'{type(exc).__name__}: {exc}'
        for values in result.buses.values():
            values.update(energized=False, voltage_v=None)
        for values in result.branches.values():
            values.update(energized=False, current_a=None, p_w=None, q_var=None, loading_pct=None)
        result.source_p_w = result.source_q_var = result.loss_w = result.power_balance_residual_w = None
        return result


def _pandapower(inputs, reached, iterations):
    import pandapower as pp
    net = pp.create_empty_network(f_hz=50)
    ids = {'source': pp.create_bus(net, vn_kv=NOMINAL_V/1000)}
    for name in inputs.feeders_closed:
        ids[name] = pp.create_bus(net, vn_kv=NOMINAL_V/1000)
        
    pp.create_ext_grid(net, ids['source'], vm_pu=1)
    q_factor = math.tan(math.acos(inputs.power_factor))
    lines = {}
    for name in inputs.feeders_closed:
        if name not in reached:
            continue
        max_i = inputs.feeder_ratings_a.get(name, 10.0) / 1000
        lines[name] = pp.create_line_from_parameters(net, ids['source'], ids[name], length_km=1,
            r_ohm_per_km=inputs.resistance_ohm, x_ohm_per_km=inputs.reactance_ohm,
            c_nf_per_km=0, max_i_ka=max_i)
        watts = inputs.loads_w.get(name, 0)
        pp.create_load(net, ids[name], p_mw=watts/1e6, q_mvar=watts*q_factor/1e6)
    pp.runpp(net, algorithm='nr', numba=False, max_iteration=iterations, tolerance_mva=1e-10, check_connectivity=True)
    if not net.converged:
        raise ValueError('AC solve did not converge')
    buses = {name: float(net.res_bus.at[ids[name], 'vm_pu'])*NOMINAL_V for name in reached}
    branches = {name: {'current_a': float(net.res_line.at[idx, 'i_from_ka'])*1000,
        'p_w': float(net.res_line.at[idx, 'p_from_mw'])*1e6,
        'q_var': float(net.res_line.at[idx, 'q_from_mvar'])*1e6,
        'loading_pct': float(net.res_line.at[idx, 'loading_percent'])} for name, idx in lines.items()}
    return buses, branches, float(net.res_ext_grid.p_mw.sum())*1e6, float(net.res_ext_grid.q_mvar.sum())*1e6


def _pgm(inputs, reached, iterations):
    from power_grid_model import initialize_array, PowerGridModel, LoadGenType, CalculationMethod
    from power_grid_model.validation import assert_valid_input_data
    feeders = list(inputs.feeders_closed.keys())
    n = len(feeders)
    node = initialize_array('input', 'node', n + 1)
    node['id'] = list(range(n + 1))
    node['u_rated'] = NOMINAL_V
    
    line = initialize_array('input', 'line', n)
    line['id'] = [10 + i for i in range(n)]
    line['from_node'] = [0] * n
    line['to_node'] = [i + 1 for i in range(n)]
    
    closed = [inputs.feeders_closed[f] for f in feeders]
    line['from_status'] = closed
    line['to_status'] = closed
    line['r1'] = inputs.resistance_ohm
    line['x1'] = inputs.reactance_ohm
    line['c1'] = 0
    line['tan1'] = 0
    line['i_n'] = [inputs.feeder_ratings_a.get(f, 10.0) for f in feeders]
    
    load = initialize_array('input', 'sym_load', n)
    load['id'] = [20 + i for i in range(n)]
    load['node'] = [i + 1 for i in range(n)]
    load['status'] = [1] * n
    load['type'] = LoadGenType.const_power
    load['p_specified'] = [inputs.loads_w.get(f, 0) for f in feeders]
    load['q_specified'] = load['p_specified'] * math.tan(math.acos(inputs.power_factor))
    
    source = initialize_array('input', 'source', 1)
    source['id'], source['node'], source['status'], source['u_ref'] = [30], [0], [1], [1.0]
    source['sk'], source['rx_ratio'] = 1e20, .1
    
    data = dict(node=node, line=line, sym_load=load, source=source)
    assert_valid_input_data(data, calculation_type=0, symmetric=True)
    output = PowerGridModel(data, system_frequency=50).calculate_power_flow(symmetric=True,
        calculation_method=CalculationMethod.newton_raphson, error_tolerance=1e-10, max_iterations=iterations)
        
    buses = {}
    if 'source' in reached or True: # source is always 0
        buses['source'] = float(output['node'][0]['u'])
    for i, name in enumerate(feeders):
        if name in reached:
            buses[name] = float(output['node'][i+1]['u'])
            
    branches = {}
    for i, name in enumerate(feeders):
        if name in reached:
            branches[name] = {'current_a': float(output['line'][i]['i_from']), 'p_w': float(output['line'][i]['p_from']),
                'q_var': float(output['line'][i]['q_from']), 'loading_pct': float(output['line'][i]['loading'])*100}
    return buses, branches, float(output['source'][0]['p']), float(output['source'][0]['q'])


def telemetry(result, sequence):
    from app.diagnosis.observations import validate
    now = datetime.fromisoformat(result.observed_at)
    raw = [('SRC', 'bus_voltage_v', result.buses.get('source', {}).get('voltage_v'), 'V')]
    for name in result.inputs.feeders_closed:
        raw += [(name, 'feeder_voltage_v', result.buses.get(name, {}).get('voltage_v'), 'V'),
                (name, 'feeder_current_a', result.branches.get(name, {}).get('current_a'), 'A')]
    assets = {'SRC'} | set(result.inputs.feeders_closed.keys())
    return [validate(dict(asset_id=asset, quantity=quantity, value=value, unit=unit, sequence=sequence,
            observed_at=now, received_at=now, provenance=result.provenance), assets, now) for asset, quantity, value, unit in raw if value is not None]


def diagnose_study(result):
    from app.diagnosis.infer import ObservationWindow, FeederRating, diagnose_campus
    window = ObservationWindow()
    observations = telemetry(result, 1)
    for observation in observations:
        window.add(observation)
    feeders = list(result.inputs.feeders_closed.keys())
    diagnosis = diagnose_campus(window, 'SRC', feeders, FeederRating(nominal_v=NOMINAL_V),
                                datetime.fromisoformat(result.observed_at))
    diagnosis['current_alarms'] = [name for name in feeders
        if result.branches.get(name, {}).get('current_a') is not None and result.branches[name]['current_a'] > result.inputs.feeder_ratings_a.get(name, 10.0)]
    diagnosis['current_alarm_meaning'] = 'Observed current exceeds configured ampacity; one-sample alarm, not a confirmed root cause.'
    return diagnosis


class ElectricalStudyResponse(BaseModel):
    site: dict
    result: ElectricalResult
    diagnosis: dict
