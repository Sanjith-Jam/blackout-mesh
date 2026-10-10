import { HospitalDemoSnapshot, HospitalDemoTransformer } from '../types';
import './ClassroomBlueprint.css';
import { EDGE_FOOTNOTE, EDGE_LABEL, EdgeLegend, PowerWire, edgeIndex } from './PowerEdges';

type Props = { snapshot: HospitalDemoSnapshot; connected: boolean };

export default function HospitalBlueprint({ snapshot, connected }: Props) {
  const edges = edgeIndex(snapshot.edges);
  // Every wire is one canonical edge from the backend (#23).
  const wire = (edgeId: string, d: string, main = false) => <PowerWire key={edgeId} edge={edges[edgeId]} d={d} main={main} live={connected} />;

  const zones: { zone: string; label: string; equipment: { id: string; name: string; label: string }[] }[] = [
    { zone: 'ICU', label: 'ICU', equipment: [
      { id: 'ventilator', name: 'Ventilator', label: 'VENTILATOR' },
      { id: 'monitor', name: 'Patient Monitor', label: 'MONITOR' },
      { id: 'infusion', name: 'Infusion Pump', label: 'INFUSION' },
      { id: 'lights', name: 'Emergency Lights', label: 'LIGHTS' },
      { id: 'oxygen', name: 'O₂ System', label: 'O₂ SYSTEM' },
    ]},
    { zone: 'Theatre', label: 'THEATRE', equipment: [
      { id: 'surgical_light', name: 'Surgical Light', label: 'SURG LIGHT' },
      { id: 'anesthesia', name: 'Anesthesia Unit', label: 'ANESTHESIA' },
      { id: 'esu', name: 'Electrosurgical', label: 'ESU' },
      { id: 'monitor', name: 'Vital Monitor', label: 'MONITOR' },
      { id: 'ac', name: 'Climate Control', label: 'HVAC' },
    ]},
    { zone: 'Wards', label: 'WARDS', equipment: [
      { id: 'bed_lights', name: 'Bed Lights', label: 'BED LIGHTS' },
      { id: 'nurse_call', name: 'Nurse Call', label: 'NURSE CALL' },
      { id: 'fans', name: 'Ceiling Fans', label: 'FANS' },
      { id: 'water_pump', name: 'Water Pump', label: 'WATER PUMP' },
      { id: 'ac', name: 'Air Conditioning', label: 'AC' },
    ]},
  ];

  const txMap: Record<string, HospitalDemoTransformer> = {};
  for (const tx of snapshot.transformers) txMap[tx.zone] = tx;

  return <section className={`power-map ${connected ? '' : 'is-stale'}`} aria-label="Hospital electricity map">
    <header className="power-map__toolbar"><div><span className="power-map__eyebrow">Hospital / electrical layer</span><h2>Follow the current</h2></div><EdgeLegend stale={!connected} /></header>
    <div className="power-map__viewport" tabIndex={0} role="region" aria-label="Scrollable hospital power map">
      <svg className="power-map__drawing" viewBox="0 0 1080 520" role="img" aria-label="Three hospital zones connected through transformers to a virtual utility supply.">
        <defs>
          <pattern id="hosp-tiles" width="20" height="20" patternUnits="userSpaceOnUse"><rect width="20" height="20" fill="#e8ece8" /><path d="M20 0H0V20" fill="none" stroke="#d0d6d0" strokeWidth=".7" /></pattern>
          <pattern id="zone-tiles" width="20" height="20" patternUnits="userSpaceOnUse"><rect width="20" height="20" fill="#eaf0ed" /><path d="M20 0H0V20" fill="none" stroke="#d4ddd7" strokeWidth=".8" /></pattern>
        </defs>
        <rect width="1080" height="520" fill="url(#hosp-tiles)" />
        <text x="30" y="26" className="power-map__map-note">HOSPITAL CAMPUS / POWER DISTRIBUTION</text>

        {/* Main supply bus */}
        {wire('hospital:SUPPLY>BUS', 'M150 465H1040', true)}

        {zones.map((z, index) => {
          const x = 30 + index * 350;
          const tx = txMap[z.zone];
          const txId = tx?.id ?? `TX${index + 1}`;
          const energized = edges[`hospital:BUS>${txId}`]?.state === 'ENERGIZED';
          const severity = tx?.diagnosis.severity ?? 'unknown';
          const outputV = tx?.sensors.output_voltage_v;
          const current = tx?.sensors.current_a;
          const temp = tx?.sensors.temperature_c;
          const coolingOk = tx?.sensors.cooling_ok;
          const eqOn = (k: number) => edges[`hospital:${txId}>${z.equipment[k].id}`]?.state === 'ENERGIZED';
          const [on1, on2, on3, on4, on5] = [0, 1, 2, 3, 4].map(eqOn);

          return <g key={z.zone}>
            {/* Zone building */}
            <rect x={x + 4} y="51" width="320" height="310" fill="#b8c4b8" />
            <rect x={x} y="46" width="320" height="310" fill="url(#zone-tiles)" stroke={severity === 'normal' ? '#5a7a5e' : severity === 'high' || severity === 'critical' ? '#9c4444' : severity === 'medium' ? '#8a7530' : '#6b7280'} strokeWidth="8" />

            {/* Zone header bar */}
            <rect x={x + 120} y="56" width="90" height="12" fill={severity === 'normal' ? '#52786a' : severity === 'high' || severity === 'critical' ? '#8b3838' : severity === 'medium' ? '#7a6520' : '#5a6370'} stroke={severity === 'normal' ? '#365346' : '#444'} strokeWidth="2" />

            {/* Zone name */}
            <text x={x + 12} y="72" className="power-map__room-name">{z.zone}</text>
            <text x={x + 12} y="88" className="power-map__map-note">{tx ? tx.diagnosis.code.replace(/_/g, ' ') : 'NO DATA'}</text>

            {/* Transformer box */}
            <rect x={x + 240} y="62" width="68" height="48" rx="4" fill={energized ? '#4a6e50' : '#6b6b6b'} stroke={energized ? '#2d4a32' : '#444'} strokeWidth="2" />
            <text x={x + 274} y="80" textAnchor="middle" fill="#e8f0ea" style={{ fontSize: '8px', fontWeight: 800, fontFamily: 'ui-monospace, monospace' }}>{tx?.id ?? '?'}</text>
            <text x={x + 274} y="96" textAnchor="middle" fill="#c4daca" style={{ fontSize: '6px', fontWeight: 600, fontFamily: 'ui-monospace, monospace' }}>{current != null ? `${current.toFixed(0)}A` : '—'} / {temp != null ? `${temp.toFixed(0)}°C` : '—'}</text>
            <text x={x + 274} y="106" textAnchor="middle" fill="#c4daca" style={{ fontSize: '5px', fontWeight: 700, fontFamily: 'ui-monospace, monospace' }}>SIM SENSOR</text>

            {/* Feed wire from bus into zone */}
            {wire(`hospital:BUS>${txId}`, `M${x + 32} 465V106`, true)}

            {/* Equipment 1 — top left (critical) */}
            {wire(`hospital:${txId}>${z.equipment[0].id}`, `M${x + 32} 120H${x + 95}`)}
            <g className={`power-map__lamp ${on1 ? 'is-on' : ''}`} transform={`translate(${x + 95} 120)`}>
              {on1 && <rect x="-27" y="-21" width="54" height="42" rx="8" fill="#95d6a4" opacity=".35" />}
              <rect x="-18" y="-8" width="36" height="16" rx="3" fill={on1 ? '#5cb86e' : '#a6aaa2'} stroke="#3a6640" strokeWidth="2" />
              {on1 && <circle cx="0" cy="0" r="3" fill="#fff" />}
              <text y="28" textAnchor="middle" className="power-map__fixture-label">{z.equipment[0].label}</text>
            </g>

            {/* Equipment 2 — top right */}
            {wire(`hospital:${txId}>${z.equipment[1].id}`, `M${x + 32} 106H${x + 220}V120`)}
            <g transform={`translate(${x + 220} 120)`}>
              <rect x="-22" y="-12" width="44" height="28" rx="3" fill={on2 ? '#68b6c2' : '#7c8581'} stroke="#3c585b" strokeWidth="2" />
              <rect x="-16" y="-7" width="32" height="16" rx="2" fill={on2 ? '#8cd6e0' : '#6c797b'} />
              {on2 && <>
                <path d="M-10 3h5l2-6 3 10 3-4h4" fill="none" stroke="#1a5a64" strokeWidth="1.5" />
              </>}
              <text y="30" textAnchor="middle" className="power-map__fixture-label">{z.equipment[1].label}</text>
            </g>

            {/* Equipment 3 — middle left */}
            {wire(`hospital:${txId}>${z.equipment[2].id}`, `M${x + 32} 200H${x + 88}`)}
            <g transform={`translate(${x + 88} 200)`}>
              <rect x="-18" y="-14" width="36" height="28" rx="3" fill={on3 ? '#5d8e79' : '#969c92'} stroke="#3a5c48" strokeWidth="2" />
              {on3 && <rect x="-10" y="-8" width="8" height="16" rx="1" fill="#a8e6c2" />}
              {on3 && <path d="M2 -6v12M6 -4v8" stroke="#4a8a6a" strokeWidth="2" />}
              <text y="28" textAnchor="middle" className="power-map__fixture-label">{z.equipment[2].label}</text>
            </g>

            {/* Equipment 4 — middle right */}
            {wire(`hospital:${txId}>${z.equipment[3].id}`, `M${x + 32} 260H${x + 210}V200H${x + 270}`)}
            <g transform={`translate(${x + 270} 200)`}>
              {on4 && <rect x="-27" y="-21" width="54" height="42" rx="8" fill="#ffe295" opacity=".35" />}
              <rect x="-18" y="-8" width="36" height="16" rx="2" fill={on4 ? '#ffdc64' : '#a6aaa2'} stroke="#797762" strokeWidth="2" />
              <text y="28" textAnchor="middle" className="power-map__fixture-label">{z.equipment[3].label}</text>
            </g>

            {/* Equipment 5 — bottom */}
            {wire(`hospital:${txId}>${z.equipment[4].id}`, `M${x + 32} 300H${x + 280}V280`)}
            <g transform={`translate(${x + 280} 270)`}>
              <rect x="-20" y="-12" width="40" height="25" fill="#e1e1d8" stroke="#7c8880" strokeWidth="2" />
              <path d="M-14 3h28m-28 5h28" stroke={on5 ? '#53998f' : '#a2a79f'} strokeWidth="2" />
              {on5 && connected && <path className="power-map__air" d="M-12 18v14M0 18v14M12 18v14" />}
              <text y="50" textAnchor="middle" className="power-map__fixture-label">{z.equipment[4].label}</text>
            </g>

            {/* Cooling indicator */}
            <g transform={`translate(${x + 65} 340)`}>
              <rect x="-7" y="-10" width="14" height="20" fill={coolingOk ? '#6abca0' : coolingOk === false ? '#c45c5c' : '#a2aaa1'} stroke="#5f7569" strokeWidth="2" />
              <circle r="2" fill={coolingOk ? '#d9fff0' : coolingOk === false ? '#ffd0d0' : '#d0d4cb'} />
            </g>

            {/* Panel breaker box */}
            <rect x={x + 20} y="300" width="24" height="29" fill="#e1c971" stroke="#8e7d40" strokeWidth="2" />
            <path d={`m${x + 34} 304-9 12h7l-4 9 12-14h-7Z`} fill="#82632b" />

            {/* Zone summary */}
            <text x={x + 80} y="380" className="power-map__feed-label">{outputV != null ? `${outputV.toFixed(0)} V SIM SENSOR` : '— V (NO READING)'} / {severity === 'normal' ? 'ALL SYSTEMS' : severity.toUpperCase()}</text>
          </g>;
        })}

        {/* Utility source box */}
        <g transform="translate(25 436)">
          <rect width="125" height="56" fill="#4a6e50" stroke="#2d4a32" strokeWidth="3" />
          <rect x="9" y="10" width="22" height="35" fill="#365840" />
          <path d="M13 19h14m-14 7h14m-14 7h14" stroke="#a7b6a6" strokeWidth="2" />
          <text x="40" y="24" className="power-map__source-text">UTILITY</text>
          <text x="40" y="42" className="power-map__source-text">{snapshot.transformers[0]?.sensors.input_voltage_v?.toFixed(0) ?? '—'} V IN</text>
        </g>
        <text x="180" y="500" className="power-map__map-note">UTILITY SUPPLY → TRANSFORMERS → ZONE DISTRIBUTION → EQUIPMENT</text>
      </svg>
    </div>

    {/* Status ledger */}
    <div className="power-map__room-ledger">
      {zones.map(z => {
        const tx = txMap[z.zone];
        const txId = tx?.id ?? '';
        const severity = tx?.diagnosis.severity ?? 'unknown';
        return <article key={z.zone} className={severity !== 'normal' && severity !== 'unknown' ? 'is-selected' : ''} aria-label={`${z.zone} equipment status`}>
          <header><strong>{z.zone}</strong><span>{tx ? tx.diagnosis.code.replace(/_/g, ' ') : 'Unknown'}</span></header>
          <div className="power-map__loads">
            {z.equipment.map(eq => {
              const e = edges[`hospital:${txId}>${eq.id}`];
              const state = e?.state ?? 'UNKNOWN';
              return <span key={eq.id} data-edge-state={state} className={state === 'ENERGIZED' ? 'is-on' : 'is-off'} title={`${eq.name} — ${e?.reason ?? 'no edge data'}`}>
                <i />{eq.name}<b>{EDGE_LABEL[state]}</b>
              </span>
            })}
            <span className={tx?.sensors.cooling_ok ? 'is-on' : 'is-off'} title="Cooling system">
              <i />Cooling<b>{tx?.sensors.cooling_ok == null ? '—' : tx.sensors.cooling_ok ? 'OK' : 'FAIL'}</b>
            </span>
          </div>
        </article>;
      })}
    </div>
    <p className="power-map__footnote">{EDGE_FOOTNOTE}</p>
  </section>;
}
