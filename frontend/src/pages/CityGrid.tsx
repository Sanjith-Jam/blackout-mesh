import { Droplets, Hospital, Lightbulb, School, Zap } from 'lucide-react';
import type { Snapshot } from '../types';

export function feederState(snapshot: Snapshot, id: string): 'OPEN' | 'CLOSED' | 'UNKNOWN' {
  const inputs = snapshot.allocation.explanation?.replay_inputs as { feeder_available?: Record<string, unknown> } | undefined;
  const available = inputs?.feeder_available?.[id];
  return available === false ? 'OPEN' : available === true ? 'CLOSED' : 'UNKNOWN';
}

const ICONS = [Hospital, Lightbulb, Droplets, School, School, School];

export default function CityGrid({ snapshot, selected, onSelect }: {
  snapshot: Snapshot; selected: string; onSelect: (id: string) => void;
}) {
  const { services, source } = snapshot;
  const feederOpen = (id: string) => feederState(snapshot, id) !== 'CLOSED';
  const served = (feeder: string) => services.filter(s => s.feeder === feeder && s.modeled_served).reduce((sum, s) => sum + s.watts, 0);
  return <section className="city-panel city-map-panel" aria-label="City electrical grid">
    <header className="city-panel-heading"><div><h2>One city, one grid</h2><p>Illustrative city blocks · six-service 14 kW lab model</p></div><span>Revision <b data-testid="city-revision">{snapshot.site?.revision}</b></span></header>
    <div className="city-map" aria-label="Select a city service to inspect its power decision">
      <svg className="city-map-drawing" viewBox="0 0 1000 460" aria-hidden="true">
        <defs><pattern id="city-paper" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="currentColor" opacity=".06" /></pattern></defs>
        <rect width="1000" height="460" fill="url(#city-paper)" />
        <path className="city-road" d="M0 230H1000M200 0V460M460 0V460M620 0V460M790 0V460M950 0V460" />
        {[520, 690, 850].map(x => <g key={x}><rect className="city-block" x={x - 50} y="35" width="125" height="135" rx="12" /><rect className="city-block" x={x - 50} y="290" width="125" height="135" rx="12" /></g>)}
        {['A', 'B'].map((feeder, row) => {
          const y = row ? 335 : 115;
          const open = feederOpen(feeder);
          return <g key={feeder}><path className={`city-wire ${!open && served(feeder) ? 'is-powered' : 'is-open'}`} d={`M110 230H275V${y}H350`} />
            {services.filter(s => s.feeder === feeder).map((service, i) => <path key={service.id} className={`city-wire ${service.modeled_served && !open ? 'is-powered' : 'is-open'}`} d={`M350 ${y}V${row ? 255 : 205}H${540 + i * 170}V${y}`} />)}
          </g>;
        })}
      </svg>
      <div className="city-source" style={{ left: '3%', top: '40%' }}><Zap size={24} aria-hidden="true" /><strong>City source</strong><b>{source.capacity_w.toLocaleString()} W</b><span>Synthetic supply</span></div>
      {['A', 'B'].map((feeder, row) => <div className={`city-substation ${feederOpen(feeder) ? 'is-outage' : ''}`} key={feeder} style={{ left: '27%', top: row ? '64%' : '16%' }}>
        <strong>Feeder {feeder}</strong><span>{{ OPEN: 'Tripped · no supply', CLOSED: 'Energized', UNKNOWN: 'Unknown' }[feederState(snapshot, feeder)]}</span><b>{served(feeder).toLocaleString()} / {snapshot.feeder_limits_w[feeder].toLocaleString()} W</b>
      </div>)}
      {services.map((service, i) => {
        const Icon = ICONS[i] ?? School;
        const status = !service.requested ? 'Not requested' : service.modeled_served ? 'Served' : 'Shed';
        return <button key={service.id} className={`city-building ${service.modeled_served ? 'is-served' : service.requested ? 'is-shed' : 'is-idle'}`} style={{ left: `${48 + (i % 3) * 17}%`, top: i < 3 ? '10%' : '65%' }}
          aria-label={`${service.name}: ${status}`} aria-pressed={selected === service.id} onClick={() => onSelect(service.id)}>
          <Icon size={24} aria-hidden="true" /><strong>{service.name}</strong><span>{service.watts.toLocaleString()} W · {service.tier}</span><b>{status}</b>
        </button>;
      })}
    </div>
    <p className="city-legend"><span className="city-dot is-served" /> Served <span className="city-dot is-shed" /> Shed / open <span className="city-dot is-idle" /> Not requested · Select any building for its reason.</p>
  </section>;
}
