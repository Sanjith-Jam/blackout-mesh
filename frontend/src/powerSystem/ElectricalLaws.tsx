import { useId, useState } from 'react';
import { CapacityBar } from './Charts';
import { energy, fmt, kclResidual, ohmCurrent, powerI2R, powerV2R, powerVI, seriesLoop, singlePhaseCurrent,
  singlePhaseRealPower, threePhaseRealPower } from './laws';
import { w } from './model';
import type { PowerSystem } from './model';

/** Educational, interactive circuit illustrations. Values marked EDUCATIONAL EXAMPLE are user-chosen inputs to the
 * equations; values marked LIVE MODEL come from the backend projection. The simulator models watts only: it has no
 * measured voltage, current or resistance, so none is ever presented as measured. */

function Tag({ kind }: { kind: 'example' | 'live' | 'derived' }) {
  const text = { example: 'EDUCATIONAL EXAMPLE', live: 'LIVE MODEL VALUES', derived: 'DERIVED FROM MODEL UNDER STATED ASSUMPTION' }[kind];
  return <span className={`ps-tag tag-${kind}`}>{text}</span>;
}

function Slider({ label, value, min, max, step, unit, onChange }: { label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void }) {
  const id = useId();
  return <div className="ps-slider"><label htmlFor={id}>{label}: <b>{fmt(value)} {unit}</b></label>
    <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(Number(e.target.value))} /></div>;
}

/** A current-flow path: dash speed follows the current magnitude; reduced-motion users see a static path. */
function Flow({ d, current, maxCurrent = 10 }: { d: string; current: number | null; maxCurrent?: number }) {
  const speed = current && current > 0 ? Math.max(0.4, 4 - (3.6 * Math.min(current, maxCurrent)) / maxCurrent) : 0;
  return <><path d={d} className="ps-circuit-wire" />{speed > 0 && <path d={d} className="ps-circuit-flow" style={{ animationDuration: `${speed}s` }} />}</>;
}

function Resistor({ x, y, label, vertical }: { x: number; y: number; label: string; vertical?: boolean }) {
  const zig = vertical ? `M${x} ${y - 24} l0 6 l8 3 l-16 6 l16 6 l-16 6 l8 3 l0 6` : `M${x - 24} ${y} l6 0 l3 -8 l6 16 l6 -16 l6 16 l3 -8 l6 0`;
  return <g className="ps-component"><path d={zig} /><text className="ps-small" x={vertical ? x + 14 : x - 10} y={vertical ? y + 4 : y - 14}>{label}</text></g>;
}

function Battery({ x, y, label }: { x: number; y: number; label: string }) {
  return <g className="ps-component"><path d={`M${x - 12} ${y - 6} h24 M${x - 6} ${y + 6} h12`} strokeWidth={3} /><text className="ps-small" x={x + 18} y={y + 4}>{label}</text></g>;
}

export function OhmsLaw() {
  const [v, setV] = useState(12), [r, setR] = useState(6);
  const i = ohmCurrent(v, r);
  return <article className="ps-law" id="law-ohm" aria-labelledby="law-ohm-h">
    <header><h3 id="law-ohm-h">1 · Ohm's law</h3><Tag kind="example" /></header>
    <p className="ps-equation">V = I × R</p>
    <div className="ps-law-body">
      <svg viewBox="0 0 260 160" role="img" aria-label={`Circuit: ${fmt(v)} volt source across a ${fmt(r)} ohm resistor; current ${fmt(i)} amperes`}>
        <Flow d="M40 130 V30 H220 V130 H40" current={i} />
        <Battery x={40} y={80} label={`${fmt(v)} V`} />
        <Resistor x={130} y={30} label={`R = ${fmt(r)} Ω`} />
        <g className="ps-component"><circle cx={220} cy={80} r={14} /><text x={220} y={85} textAnchor="middle" className="ps-small strong">A</text></g>
        <text className="ps-small" x={150} y={150}>{`I = ${fmt(i)} A`}</text>
      </svg>
      <div><Slider label="Voltage V" value={v} min={0} max={48} step={0.5} unit="V" onChange={setV} />
        <Slider label="Resistance R" value={r} min={1} max={48} step={0.5} unit="Ω" onChange={setR} />
        <p className="ps-result">I = V ÷ R = {fmt(v)} V ÷ {fmt(r)} Ω = <b>{fmt(i, 3)} A</b></p>
        <p className="ps-muted">Doubling V doubles I; doubling R halves it. Holds for an ideal linear resistor in a DC circuit (or a purely resistive AC load with RMS values).</p></div>
    </div>
    <p className="ps-note">Model link: PriorityGrid configures appliance demand in watts only. It has no resistance or current values, so this circuit uses example values, not measurements.</p>
  </article>;
}

export function PowerLaw({ data }: { data: PowerSystem }) {
  const [mode, setMode] = useState<'dc' | 'single' | 'three'>('single');
  const [v, setV] = useState(12), [r, setR] = useState(6);
  const [vr, setVr] = useState(230), [ir, setIr] = useState(5), [pf, setPf] = useState(0.95);
  const [vl, setVl] = useState(400), [il, setIl] = useState(10);
  const [applianceId, setApplianceId] = useState(data.appliances[0]?.id ?? '');
  const appliance = data.appliances.find(a => a.id === applianceId);
  const i = ohmCurrent(v, r);
  const id = useId();
  return <article className="ps-law" id="law-power" aria-labelledby="law-power-h">
    <header><h3 id="law-power-h">2 · Electrical power</h3><Tag kind="example" /></header>
    <div className="ps-segmented" role="radiogroup" aria-label="Circuit model">
      {([['dc', 'DC / resistive'], ['single', 'Single-phase AC'], ['three', 'Balanced three-phase']] as const).map(([k, label]) =>
        <button key={k} role="radio" aria-checked={mode === k} className={mode === k ? 'is-active' : ''} onClick={() => setMode(k)}>{label}</button>)}
    </div>
    {mode === 'dc' && <div className="ps-law-body"><div>
      <p className="ps-equation">P = V × I = I² × R = V² ÷ R</p>
      <Slider label="Voltage V" value={v} min={0} max={48} step={0.5} unit="V" onChange={setV} />
      <Slider label="Resistance R" value={r} min={1} max={48} step={0.5} unit="Ω" onChange={setR} />
      <table className="ps-table"><tbody>
        <tr><th>V × I</th><td>{fmt(v)} × {fmt(i, 3)}</td><td><b>{fmt(powerVI(v, i ?? NaN))} W</b></td></tr>
        <tr><th>I² × R</th><td>{fmt(i, 3)}² × {fmt(r)}</td><td><b>{fmt(powerI2R(i ?? NaN, r))} W</b></td></tr>
        <tr><th>V² ÷ R</th><td>{fmt(v)}² ÷ {fmt(r)}</td><td><b>{fmt(powerV2R(v, r))} W</b></td></tr></tbody></table>
      <p className="ps-muted">Assumptions: DC, or AC with a purely resistive load and RMS values. The three forms agree only because V = I × R holds.</p></div></div>}
    {mode === 'single' && <div className="ps-law-body"><div>
      <p className="ps-equation">P = V × I × PF</p>
      <Slider label="RMS voltage V" value={vr} min={100} max={250} step={1} unit="V" onChange={setVr} />
      <Slider label="RMS current I" value={ir} min={0} max={20} step={0.1} unit="A" onChange={setIr} />
      <Slider label="Power factor PF" value={pf} min={0.5} max={1} step={0.01} unit="" onChange={setPf} />
      <p className="ps-result">P = {fmt(vr)} V × {fmt(ir)} A × {fmt(pf)} = <b>{fmt(singlePhaseRealPower(vr, ir, pf), 1)} W</b> real power</p>
      <p className="ps-muted">Assumptions: sinusoidal single-phase supply, RMS values, PF = cos φ between voltage and current.</p></div>
      <div className="ps-derived"><Tag kind="derived" />
        <label htmlFor={id}>Configured appliance</label>
        <select id={id} value={applianceId} onChange={e => setApplianceId(e.target.value)}>
          {data.appliances.map(a => <option key={a.id} value={a.id}>{a.room_id} · {a.name} ({w(a.demand_w)})</option>)}</select>
        {appliance && <p className="ps-result">If {appliance.name} drew its configured {w(appliance.demand_w)} from a 230 V single-phase supply at PF {fmt(pf)}, then I = P ÷ (V × PF) = <b>{fmt(singlePhaseCurrent(appliance.demand_w, 230, pf), 2)} A</b>.</p>}
        <p className="ps-muted">The hospital transformer telemetry in this simulator is generated as served watts ÷ 230 V (unity power factor). That current is simulated, not measured.</p></div></div>}
    {mode === 'three' && <div className="ps-law-body"><div>
      <p className="ps-equation">P = √3 × V<sub>L</sub> × I<sub>L</sub> × PF</p>
      <Slider label="Line-to-line voltage V_L" value={vl} min={200} max={480} step={1} unit="V" onChange={setVl} />
      <Slider label="Line current I_L" value={il} min={0} max={40} step={0.1} unit="A" onChange={setIl} />
      <Slider label="Power factor PF" value={pf} min={0.5} max={1} step={0.01} unit="" onChange={setPf} />
      <p className="ps-result">P = 1.732 × {fmt(vl)} V × {fmt(il)} A × {fmt(pf)} = <b>{fmt(threePhaseRealPower(vl, il, pf), 1)} W</b></p>
      <p className="ps-muted">Assumptions: balanced three-phase load, line quantities, identical PF on every phase. Do not mix with the single-phase formula: a single-phase load sees V<sub>phase</sub> = V<sub>L</sub> ÷ √3.</p></div></div>}
  </article>;
}

export function KirchhoffCurrent({ data }: { data: PowerSystem }) {
  const [b1, setB1] = useState(4), [b2, setB2] = useState(3.5), [b3, setB3] = useState(2.5);
  const entering = b1 + b2 + b3;
  return <article className="ps-law" id="law-kcl" aria-labelledby="law-kcl-h">
    <header><h3 id="law-kcl-h">3 · Kirchhoff's current law</h3><Tag kind="example" /></header>
    <p className="ps-equation">Σ I<sub>in</sub> = Σ I<sub>out</sub></p>
    <div className="ps-law-body">
      <svg viewBox="0 0 260 160" role="img" aria-label={`Junction: ${fmt(entering)} amperes in, branches ${fmt(b1)}, ${fmt(b2)} and ${fmt(b3)} amperes out`}>
        <Flow d="M10 80 H120" current={entering} maxCurrent={30} />
        <Flow d="M120 80 L230 25" current={b1} /><Flow d="M120 80 H230" current={b2} /><Flow d="M120 80 L230 135" current={b3} />
        <circle cx={120} cy={80} r={8} className="ps-junction" />
        <text className="ps-small strong" x={20} y={70}>{`${fmt(entering)} A in`}</text>
        <text className="ps-small" x={180} y={22}>{`${fmt(b1)} A`}</text><text className="ps-small" x={190} y={74}>{`${fmt(b2)} A`}</text><text className="ps-small" x={180} y={150}>{`${fmt(b3)} A`}</text>
      </svg>
      <div><Slider label="Branch 1" value={b1} min={0} max={10} step={0.1} unit="A" onChange={setB1} />
        <Slider label="Branch 2" value={b2} min={0} max={10} step={0.1} unit="A" onChange={setB2} />
        <Slider label="Branch 3" value={b3} min={0} max={10} step={0.1} unit="A" onChange={setB3} />
        <p className="ps-result">In {fmt(entering)} A − out ({fmt(b1)} + {fmt(b2)} + {fmt(b3)}) A = <b>{fmt(kclResidual([entering], [b1, b2, b3]), 3)} A</b></p>
        <p className="ps-muted">Assumption: lumped circuit, charge does not accumulate at the node.</p></div>
    </div>
    <div className="ps-derived"><Tag kind="live" />
      <p>The model has no branch currents, but it conserves power at every junction. Watt balance right now:</p>
      <p className="ps-result">{data.source.name}: <b>{w(data.source.served_w)}</b> = {data.feeders.map(f => `Feeder ${f.id} ${w(f.served_w)}`).join(' + ')}</p>
      <p className="ps-muted">This is the power-level analogue of KCL in the simulation, not a current measurement.</p></div>
  </article>;
}

export function KirchhoffVoltage() {
  const [v, setV] = useState(24), [r1, setR1] = useState(4), [r2, setR2] = useState(8);
  const loop = seriesLoop(v, [r1, r2]);
  return <article className="ps-law" id="law-kvl" aria-labelledby="law-kvl-h">
    <header><h3 id="law-kvl-h">4 · Kirchhoff's voltage law</h3><Tag kind="example" /></header>
    <p className="ps-equation">Σ V around a closed loop = 0</p>
    <div className="ps-law-body">
      <svg viewBox="0 0 260 160" role="img" aria-label={`Loop: ${fmt(v)} volt source, drops ${fmt(loop?.dropsV[0])} and ${fmt(loop?.dropsV[1])} volts`}>
        <Flow d="M40 130 V30 H220 V130 H40" current={loop?.currentA ?? null} />
        <Battery x={40} y={80} label={`+${fmt(v)} V`} />
        <Resistor x={130} y={30} label={`R1 ${fmt(r1)} Ω · −${fmt(loop?.dropsV[0])} V`} />
        <Resistor x={220} y={80} label="" vertical />
        <text className="ps-small" x={150} y={150}>{`R2 ${fmt(r2)} Ω · −${fmt(loop?.dropsV[1])} V`}</text>
      </svg>
      <div><Slider label="Source V" value={v} min={0} max={48} step={0.5} unit="V" onChange={setV} />
        <Slider label="R1" value={r1} min={1} max={30} step={0.5} unit="Ω" onChange={setR1} />
        <Slider label="R2" value={r2} min={1} max={30} step={0.5} unit="Ω" onChange={setR2} />
        <p className="ps-result">+{fmt(v)} V − {fmt(loop?.dropsV[0])} V − {fmt(loop?.dropsV[1])} V = <b>{fmt(loop?.residualV, 3)} V</b> (I = {fmt(loop?.currentA, 3)} A)</p>
        <p className="ps-muted">Assumptions: lumped series loop, ideal source and wires. PriorityGrid has no wire impedances, so it computes no voltage drops; this example does not describe the campus.</p></div>
    </div>
  </article>;
}

export function EnergyLaw({ data }: { data: PowerSystem }) {
  const [applianceId, setApplianceId] = useState(data.appliances.find(a => a.key === 'ventilator')?.id ?? data.appliances[0]?.id ?? '');
  const [hours, setHours] = useState(8);
  const a = data.appliances.find(x => x.id === applianceId);
  const e = a ? energy(a.demand_w, hours) : null;
  const site = energy(data.source.served_w, hours);
  const id = useId();
  return <article className="ps-law" id="law-energy" aria-labelledby="law-energy-h">
    <header><h3 id="law-energy-h">5 · Power and energy</h3><Tag kind="live" /></header>
    <p className="ps-equation">E = P × t</p>
    <div className="ps-law-body"><div>
      <label htmlFor={id}>Configured appliance (simulated demand)</label>
      <select id={id} value={applianceId} onChange={ev => setApplianceId(ev.target.value)}>
        {data.appliances.map(x => <option key={x.id} value={x.id}>{x.room_id} · {x.name} ({w(x.demand_w)})</option>)}</select>
      <Slider label="Simulated duration t" value={hours} min={0.25} max={24} step={0.25} unit="h" onChange={setHours} />
      {a && e && <table className="ps-table"><tbody>
        <tr><th>Watt-hours</th><td>{w(a.demand_w)} × {fmt(hours)} h</td><td><b>{fmt(e.wh, 1)} Wh</b></td></tr>
        <tr><th>Kilowatt-hours</th><td>{fmt(e.wh, 1)} Wh ÷ 1,000</td><td><b>{fmt(e.kwh, 3)} kWh</b></td></tr>
        <tr><th>Joules</th><td>{fmt(e.wh, 1)} Wh × 3,600 s/h</td><td><b>{fmt(e.joules, 0)} J</b></td></tr></tbody></table>}
      {site && <p className="ps-result">Whole site at the current modeled supply ({w(data.source.served_w)}) held for {fmt(hours)} h: <b>{fmt(site.kwh, 2)} kWh</b>.</p>}
      <p className="ps-muted">Assumes the configured demand stays constant for the whole duration. A watt is a rate (1 J/s); a watt-hour is an amount of energy. These are simulated configuration values, not metered consumption.</p>
    </div></div>
  </article>;
}

export function CapacityLaw({ data, emphasis }: { data: PowerSystem; emphasis?: boolean }) {
  const checks = data.constraint_checks;
  const changed = data.appliance_events.slice(-8).reverse();
  return <article className={`ps-law${emphasis ? ' is-emphasis' : ''}`} id="law-capacity" aria-labelledby="law-capacity-h">
    <header><h3 id="law-capacity-h">6 · Capacity and overload</h3><Tag kind="live" /></header>
    <p className="ps-equation">Σ P<sub>served</sub> ≤ P<sub>limit</sub> &nbsp;·&nbsp; deficit = max(0, Σ P<sub>requested</sub> − P<sub>limit</sub>)</p>
    <div className="ps-capbars">{checks.map(c => <CapacityBar key={c.id} label={c.label} requested={c.requested_w} limit={c.limit_w} served={c.served_w}
      open={c.scope === 'feeder' && !data.feeders.find(f => `feeder:${f.id}` === c.id)?.available} />)}</div>
    <p className="ps-muted">A violation is shown only when configured requested demand exceeds a configured limit. Modeled served power never exceeds a limit: the optimizer sheds appliances instead.</p>
    {changed.length > 0 && <><h4>Recent allocation changes</h4><ul className="ps-changes">{changed.map(e =>
      <li key={`${e.timestamp}-${e.appliance_id}-${e.to}`}><b>{e.appliance_id}</b> {e.from_state ?? '—'} → {e.to} <span className="ps-muted">({e.reason}{e.command ? ` after ${e.command}` : ''})</span></li>)}</ul></>}
  </article>;
}

export function ContinuityLaw({ data, emphasis }: { data: PowerSystem; emphasis?: 'open' | 'missing' }) {
  const open = data.feeders.filter(f => !f.available).map(f => f.id);
  return <article className={`ps-law${emphasis ? ' is-emphasis' : ''}`} id="law-continuity" aria-labelledby="law-continuity-h">
    <header><h3 id="law-continuity-h">7 · Circuit continuity and fault effects</h3><Tag kind="example" /></header>
    <div className="ps-before-after">
      {[['Closed circuit', false], ['Open connection', true]].map(([label, isOpen]) => <figure key={String(label)}>
        <svg viewBox="0 0 200 110" role="img" aria-label={`${label}: ${isOpen ? 'no current can flow' : 'current flows around the loop'}`}>
          <Flow d={isOpen ? 'M20 90 V20 H80' : 'M20 90 V20 H180 V90 H20'} current={isOpen ? null : 3} />
          {isOpen ? <><path d="M120 20 H180 V90 H20" className="ps-circuit-wire is-dead" /><path d="M80 20 L112 6" className="ps-switch-open" /><text x={84} y={40} className="ps-small danger">open</text></>
            : <path d="M80 20 H120" className="ps-circuit-wire" />}
          <g className="ps-component"><circle cx={150} cy={55} r={12} /><path d="M142 55 h16" /></g>
        </svg><figcaption>{label}</figcaption></figure>)}
    </div>
    <p className={emphasis === 'open' ? 'ps-result' : 'ps-muted'}>{open.length
      ? `Live model: feeder ${open.join(' and ')} is open, so every appliance downstream has no path from the source (UNREACHABLE). Loads on the other feeder keep their path.`
      : 'Live model: both feeders are closed; every appliance has a configured path from the source.'}</p>
    <table className="ps-table ps-conditions"><thead><tr><th>Condition</th><th>What it means</th><th>In this model</th></tr></thead><tbody>
      <tr><th>Electrical disconnection</th><td>No closed path: current cannot flow to downstream loads.</td><td>Modeled: feeder switch state; downstream appliances are UNREACHABLE.</td></tr>
      <tr><th>Demand exceeds capacity</th><td>The circuit is intact, but the requested power is above a limit.</td><td>Modeled: the optimizer sheds lower-priority appliances (SHED); paths stay connected.</td></tr>
      <tr><th>Short circuit</th><td>A very low-impedance path causes very high current until protection trips.</td><td>Not modeled. The simulator has no impedances or fault currents.</td></tr>
      <tr><th>Voltage deviation</th><td>Supply voltage outside its normal band (sag or swell).</td><td>Only hospital transformer telemetry carries voltages; diagnosis rules flag low input voltage.</td></tr>
      <tr className={emphasis === 'missing' ? 'is-emphasis' : ''}><th>Missing or stale telemetry</th><td>The sensor stopped reporting. That says nothing about the circuit itself.</td><td>Diagnosis abstains (INCONCLUSIVE). It is never treated as proof of an electrical failure.</td></tr>
    </tbody></table>
  </article>;
}

export default function ElectricalLaws({ data }: { data: PowerSystem }) {
  return <section className="ps-laws" aria-label="Electrical laws">
    <p className="ps-boundary">Each card says where its numbers come from. <b>Educational example</b> values are inputs you choose; <b>live model</b> values come from the backend simulation. The simulation models power in watts only.</p>
    <OhmsLaw /><PowerLaw data={data} /><KirchhoffCurrent data={data} /><KirchhoffVoltage /><EnergyLaw data={data} />
    <CapacityLaw data={data} /><ContinuityLaw data={data} />
  </section>;
}
