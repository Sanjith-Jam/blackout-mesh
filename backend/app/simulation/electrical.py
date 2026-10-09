"""Optional balanced AC studies. No control mutations, thermal model or hardware claims."""
import math
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

TOPOLOGY_VERSION = 'radial-400v-v1'
NOMINAL_V = 400.0
RATINGS_A = {'A': 10.0, 'B': 14.0}


class ElectricalInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    topology_version: Literal['radial-400v-v1'] = TOPOLOGY_VERSION
    balanced: StrictBool = True
    load_a_w: StrictInt = Field(default=6000, ge=0, le=100000)
    load_b_w: StrictInt = Field(default=8000, ge=0, le=100000)
    source_on: StrictBool = True
    feeder_a_closed: StrictBool = True
    feeder_b_closed: StrictBool = True
    power_factor: float = Field(default=.95, ge=.8, le=1, allow_inf_nan=False)
    resistance_ohm: float = Field(default=.04, gt=0, le=10, allow_inf_nan=False)
    reactance_ohm: float = Field(default=.015, ge=0, le=10, allow_inf_nan=False)

    @field_validator('balanced')
    @classmethod
    def require_balanced(cls, value):
        if not value:
            raise ValueError('only balanced positive-sequence studies are supported')
        return value


class ElectricalResult(BaseModel):
    mode: Literal['balanced_ac_study'] = 'balanced_ac_study'
    topology_version: str = TOPOLOGY_VERSION
    engine: str
    engine_version: str | None = None
    status: Literal['converged', 'deenergized', 'failed', 'unavailable']
    converged: bool
    restoration_authorized: Literal[False] = False
    observed_at: str
    inputs: ElectricalInput
    units: dict[str, str]
    buses: dict[str, dict[str, float | bool | None]]
    branches: dict[str, dict[str, float | bool | None]]
    source_p_w: float | None = None
    source_q_var: float | None = None
    loss_w: float | None = None
    power_balance_residual_w: float | None = None
    reason: str | None = None
    provenance: str = 'SIMULATED_AC_SOLVER; synthetic engineering parameters'


def reachability(inputs):
    import networkx as nx
    graph = nx.Graph()
    graph.add_nodes_from(('source', 'A', 'B'))
    for name, closed in (('A', inputs.feeder_a_closed), ('B', inputs.feeder_b_closed)):
        if closed:
            graph.add_edge('source', name)
    return set(nx.node_connected_component(graph, 'source')) if inputs.source_on else set()


def solve(inputs: ElectricalInput, engine='power-grid-model', max_iterations=30):
    """One immutable study; missing/failed/islanded values stay null, never fabricated."""
    result = ElectricalResult(engine=engine, status='failed', converged=False,
        observed_at=datetime.now(timezone.utc).isoformat(), inputs=inputs,
        units={'voltage_v': 'V line-to-line RMS', 'current_a': 'A RMS', 'p_w': 'W total three-phase',
               'q_var': 'var total three-phase', 'loading_pct': '% ampacity', 'loss_w': 'W'},
        buses={name: {'energized': False, 'voltage_v': None} for name in ('source', 'A', 'B')},
        branches={name: {'energized': False, 'current_a': None, 'p_w': None, 'q_var': None, 'loading_pct': None} for name in ('A', 'B')})
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
        served = sum(getattr(inputs, f'load_{name.lower()}_w') for name in ('A', 'B') if name in reached)
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
        # Never expose partial outputs from a failed solve.
        for values in result.buses.values():
            values.update(energized=False, voltage_v=None)
        for values in result.branches.values():
            values.update(energized=False, current_a=None, p_w=None, q_var=None, loading_pct=None)
        result.source_p_w = result.source_q_var = result.loss_w = result.power_balance_residual_w = None
        return result


def _pandapower(inputs, reached, iterations):
    import pandapower as pp
    net = pp.create_empty_network(f_hz=50)
    ids = {name: pp.create_bus(net, vn_kv=NOMINAL_V/1000) for name in ('source', 'A', 'B')}
    pp.create_ext_grid(net, ids['source'], vm_pu=1)
    q_factor = math.tan(math.acos(inputs.power_factor))
    lines = {}
    for name in ('A', 'B'):
        if name not in reached:
            continue
        lines[name] = pp.create_line_from_parameters(net, ids['source'], ids[name], length_km=1,
            r_ohm_per_km=inputs.resistance_ohm, x_ohm_per_km=inputs.reactance_ohm,
            c_nf_per_km=0, max_i_ka=RATINGS_A[name]/1000)
        watts = getattr(inputs, f'load_{name.lower()}_w')
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
    node = initialize_array('input', 'node', 3)
    node['id'], node['u_rated'] = [0, 1, 2], NOMINAL_V
    line = initialize_array('input', 'line', 2)
    line['id'], line['from_node'], line['to_node'] = [10, 11], [0, 0], [1, 2]
    closed = [inputs.feeder_a_closed, inputs.feeder_b_closed]
    line['from_status'], line['to_status'] = closed, closed
    line['r1'], line['x1'], line['c1'], line['tan1'], line['i_n'] = inputs.resistance_ohm, inputs.reactance_ohm, 0, 0, [10, 14]
    load = initialize_array('input', 'sym_load', 2)
    load['id'], load['node'], load['status'], load['type'] = [20, 21], [1, 2], [1, 1], LoadGenType.const_power
    load['p_specified'] = [inputs.load_a_w, inputs.load_b_w]
    load['q_specified'] = load['p_specified'] * math.tan(math.acos(inputs.power_factor))
    source = initialize_array('input', 'source', 1)
    source['id'], source['node'], source['status'], source['u_ref'] = [30], [0], [1], [1.0]
    source['sk'], source['rx_ratio'] = 1e20, .1  # Near-ideal source matches pandapower's ideal slack.
    data = dict(node=node, line=line, sym_load=load, source=source)
    assert_valid_input_data(data, calculation_type=0, symmetric=True)
    output = PowerGridModel(data, system_frequency=50).calculate_power_flow(symmetric=True,
        calculation_method=CalculationMethod.newton_raphson, error_tolerance=1e-10, max_iterations=iterations)
    buses = {name: float(output['node'][i]['u']) for i, name in enumerate(('source', 'A', 'B')) if name in reached}
    branches = {name: {'current_a': float(output['line'][i]['i_from']), 'p_w': float(output['line'][i]['p_from']),
        'q_var': float(output['line'][i]['q_from']), 'loading_pct': float(output['line'][i]['loading'])*100}
        for i, name in enumerate(('A', 'B')) if name in reached}
    return buses, branches, float(output['source'][0]['p']), float(output['source'][0]['q'])


def telemetry(result, sequence):
    """Pass observations only to existing diagnosis; no topology switches or fault labels."""
    from app.diagnosis.observations import validate
    now = datetime.fromisoformat(result.observed_at)
    raw = [('SRC', 'bus_voltage_v', result.buses['source']['voltage_v'], 'V')]
    for name in ('A', 'B'):
        raw += [(name, 'feeder_voltage_v', result.buses[name]['voltage_v'], 'V'),
                (name, 'feeder_current_a', result.branches[name]['current_a'], 'A')]
    assets = {'SRC', 'A', 'B'}
    return [validate(dict(asset_id=asset, quantity=quantity, value=value, unit=unit, sequence=sequence,
            observed_at=now, received_at=now, provenance=result.provenance), assets, now) for asset, quantity, value, unit in raw]


def diagnose_study(result):
    from app.diagnosis.infer import ObservationWindow, FeederRating, diagnose_campus
    window = ObservationWindow()
    observations = telemetry(result, 1)
    for observation in observations:
        window.add(observation)
    diagnosis = diagnose_campus(window, 'SRC', ['A', 'B'], FeederRating(nominal_v=NOMINAL_V),
                                datetime.fromisoformat(result.observed_at))
    diagnosis['current_alarms'] = [name for name in ('A', 'B')
        if result.branches[name]['current_a'] is not None and result.branches[name]['current_a'] > RATINGS_A[name]]
    diagnosis['current_alarm_meaning'] = 'Observed current exceeds configured ampacity; one-sample alarm, not a confirmed root cause.'
    return diagnosis


class ElectricalStudyResponse(BaseModel):
    site: dict
    result: ElectricalResult
    diagnosis: dict
