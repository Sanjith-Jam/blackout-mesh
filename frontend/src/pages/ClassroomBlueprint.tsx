import { ClassroomDemoLoad, ClassroomDemoSnapshot } from '../types';
import './ClassroomBlueprint.css';
import { EDGE_FOOTNOTE, EDGE_LABEL, EdgeLegend, PowerWire, edgeIndex } from './PowerEdges';

type Props = { snapshot: ClassroomDemoSnapshot; connected: boolean };

export default function ClassroomBlueprint({ snapshot, connected }: Props) {
  const edges = edgeIndex(snapshot.edges);
  // Every wire is one canonical edge from the backend (#23); its state, not a served flag, drives the drawing.
  const wire = (edgeId: string, d: string, main = false) => <PowerWire key={edgeId} edge={edges[edgeId]} d={d} main={main} live={connected} />;
  const loadEdge = (roomId: string, loadId: string) => edges[`classroom:${roomId}>${loadId}`];
  const status = (roomId: string, load: ClassroomDemoLoad) => EDGE_LABEL[loadEdge(roomId, load.id)?.state ?? 'UNKNOWN'];

  return <section className={`power-map ${connected ? '' : 'is-stale'}`} aria-label="Classroom electricity map">
    <header className="power-map__toolbar"><div><span className="power-map__eyebrow">Campus / electrical layer</span><h2>Follow the current</h2></div><EdgeLegend stale={!connected} /></header>
    <div className="power-map__viewport" tabIndex={0} role="region" aria-label="Scrollable campus power map">
      <svg className="power-map__drawing" viewBox="0 0 1080 460" role="img" aria-label={`Three classrooms connected to a shared simulated supply. ${snapshot.rooms.map(room => `${room.name}: ${room.loads.map(load => `${load.name} ${status(room.id, load)}`).join(', ')}`).join('. ')}`}>
        <defs>
          <pattern id="campus-tiles" width="20" height="20" patternUnits="userSpaceOnUse"><rect width="20" height="20" fill="#edece5" /><path d="M20 0H0V20" fill="none" stroke="#d9dad2" strokeWidth=".7" /></pattern>
          <pattern id="classroom-tiles" width="20" height="20" patternUnits="userSpaceOnUse"><rect width="20" height="20" fill="#f5efdd" /><path d="M20 0H0V20" fill="none" stroke="#e6dfcb" strokeWidth=".8" /></pattern>
        </defs>
        <rect width="1080" height="460" fill="url(#campus-tiles)" />
        <text x="30" y="26" className="power-map__map-note">CLASSROOM BLOCK / POWER DISTRIBUTION</text>
        {snapshot.rooms.map((room, index) => {
          const x = 30 + index * 350;
          return <g key={`${room.id}-structure`}>
            <rect x={x + 4} y="51" width="320" height="280" fill="#c6c6bc" />
            <rect x={x} y="46" width="320" height="280" fill="url(#classroom-tiles)" stroke="#747c76" strokeWidth="8" />
            <path d={`M${x + 104} 46h80M${x + 320} 106v65`} stroke="#a4c7cf" strokeWidth="7" />
            <path d={`M${x + 14} 326h40`} stroke="#edece5" strokeWidth="12" />
            <path d={`M${x + 14} 326v-35h36`} fill="none" stroke="#9e8b6c" strokeWidth="4" />
            <rect x={x + 120} y="56" width="90" height="12" fill="#52786a" stroke="#365346" strokeWidth="2" />
            <text x={x + 12} y="72" className="power-map__room-name">{room.id}</text>
            <text x={x + 12} y="88" className="power-map__map-note">{room.rfid_active ? 'RFID ACTIVE' : 'NO RECENT SCAN'}</text>
          </g>;
        })}
        {wire('classroom:SUPPLY>BUS', 'M150 408H1040', true)}
        {snapshot.rooms.map((room, index) => {
          const x = 30 + index * 350;
          const loads = Object.fromEntries(room.loads.map(load => [load.id, load]));
          const on = (id: string) => loadEdge(room.id, id)?.state === 'ENERGIZED';
          return <g key={room.id} data-room={room.id}>
            {wire(`classroom:BUS>${room.id}`, `M${x + 32} 408V96`, true)}
            {wire(`classroom:${room.id}>lighting`, `M${x + 32} 112H${x + 95}`)}
            {wire(`classroom:${room.id}>computers`, `M${x + 32} 290H${x + 132}V152H${x + 270}M${x + 132} 222H${x + 270}`)}
            {wire(`classroom:${room.id}>fans`, `M${x + 32} 192H${x + 88}`)}
            {wire(`classroom:${room.id}>projector`, `M${x + 32} 96H${x + 238}V112`)}
            {wire(`classroom:${room.id}>ac`, `M${x + 32} 298H${x + 288}V270`)}
            {loads.instruments && wire(`classroom:${room.id}>instruments`, `M${x + 32} 306H${x + 88}V264`)}
            <g className={`power-map__lamp ${on('lighting') ? 'is-on' : ''}`} transform={`translate(${x + 95} 112)`}>
              {on('lighting') && <rect x="-27" y="-21" width="54" height="42" rx="8" fill="#ffe295" opacity=".45" />}
              <rect x="-18" y="-6" width="36" height="12" fill={on('lighting') ? '#ffdc64' : '#a6aaa2'} stroke="#797762" strokeWidth="2" />
              <text y="29" textAnchor="middle" className="power-map__fixture-label">LIGHTS</text>
            </g>
            {[152, 222].map(y => [170, 250].map(dx => <g key={`${y}-${dx}`} className={`power-map__pc ${on('computers') ? 'is-on' : ''}`} transform={`translate(${x + dx} ${y})`}>
              <rect x="-28" y="-15" width="56" height="33" fill="#c7ac82" stroke="#8a775d" strokeWidth="2" />
              <rect x="-14" y="-11" width="28" height="19" fill={on('computers') ? '#68b6c2' : '#6c797b'} stroke="#3c585b" strokeWidth="3" />
              <path d="M-15 12h24" stroke="#e8ddc4" strokeWidth="3" />
              <rect x="-9" y="23" width="18" height="13" fill="#8b9c8f" stroke="#617367" strokeWidth="2" />
            </g>))}
            <text x={x + 210} y="281" textAnchor="middle" className="power-map__fixture-label">COMPUTERS</text>
            <g transform={`translate(${x + 88} 192)`}>
              <circle r="20" fill="#deded0" stroke="#8d978c" strokeWidth="2" />
              <g className={on('fans') && connected ? 'power-map__fan is-spinning' : 'power-map__fan'} fill={on('fans') ? '#5d8e79' : '#969c92'}><path d="M-3-3-6-16 2-18 5-4 16-6 18 2 4 5 6 16-2 18-5 4-16 6-18-2Z" /></g>
              <circle r="4" fill="#58675d" /><text y="34" textAnchor="middle" className="power-map__fixture-label">FAN</text>
            </g>
            <g transform={`translate(${x + 238} 112)`}>
              {on('projector') && <path d="M-7-9-36-39H36L7-9Z" fill="#b1dce2" opacity=".6" />}
              <rect x="-18" y="-10" width="36" height="20" fill="#d1d3c8" stroke="#7b857c" strokeWidth="2" /><rect x="-6" y="-10" width="12" height="6" fill={on('projector') ? '#78c5d1' : '#7c8581'} />
              <text y="28" textAnchor="middle" className="power-map__fixture-label">PROJECTOR</text>
            </g>
            <g transform={`translate(${x + 288} 260)`}>
              <rect x="-20" y="-12" width="40" height="25" fill="#e1e1d8" stroke="#7c8880" strokeWidth="2" />
              <path d="M-14 3h28m-28 5h28" stroke={on('ac') ? '#53998f' : '#a2a79f'} strokeWidth="2" />
              {on('ac') && <path className="power-map__air" d="M-12 18v14M0 18v14M12 18v14" />}
              <text y="50" textAnchor="middle" className="power-map__fixture-label">AC</text>
            </g>
            {loads.instruments && <g transform={`translate(${x + 88} 260)`}><rect x="-20" y="-14" width="40" height="28" fill="#aab2aa" stroke="#6a786e" strokeWidth="2" /><rect x="-14" y="-9" width="20" height="16" fill={on('instruments') ? '#70b9b0' : '#68716d'} /><path d="M-11 0h3l3-5 4 9 4-4" fill="none" stroke={on('instruments') ? '#b4ffee' : '#939b94'} strokeWidth="2" /><text y="31" textAnchor="middle" className="power-map__fixture-label">LAB KIT</text></g>}
            <rect x={x + 20} y="282" width="24" height="29" fill="#e1c971" stroke="#8e7d40" strokeWidth="2" /><path d={`m${x + 34} 286-9 12h7l-4 9 12-14h-7Z`} fill="#82632b" />
            <g transform={`translate(${x + 65} 318)`}><rect x="-7" y="-10" width="14" height="20" fill={room.rfid_active ? '#6abca0' : '#a2aaa1'} stroke="#5f7569" strokeWidth="2" /><circle r="2" fill={room.rfid_active ? '#d9fff0' : '#d0d4cb'} /></g>
            <text x={x + 80} y="363" className="power-map__feed-label">{room.loads.filter(load => load.served).reduce((sum, load) => sum + load.watts, 0).toLocaleString()} W MODELED / {room.rfid_active ? 'ACTIVE ROOM' : 'ESSENTIALS FIRST'}</text>
          </g>;
        })}
        <g transform="translate(25 380)"><rect width="125" height="56" fill="#677c6e" stroke="#3e5647" strokeWidth="3" /><rect x="9" y="10" width="22" height="35" fill="#3c5144" /><path d="M13 19h14m-14 7h14m-14 7h14" stroke="#a7b6a6" strokeWidth="2" /><text x="40" y="24" className="power-map__source-text">SUPPLY</text><text x="40" y="42" className="power-map__source-text">{snapshot.capacity_w.toLocaleString()} W</text></g>
        <text x="180" y="440" className="power-map__map-note">SHARED POWER BUS → ROOM PANELS → EQUIPMENT</text>
      </svg>
    </div>
    <div className="power-map__room-ledger">
      {snapshot.rooms.map(room => <article key={room.id} className={room.rfid_active ? 'is-selected' : ''} aria-label={`${room.name} equipment status`}><header><strong>{room.name}</strong><span>{room.rfid_active ? 'RFID active' : 'Unscanned'}</span></header><div className="power-map__loads">{room.loads.map(load => <span key={load.id} data-edge-state={loadEdge(room.id, load.id)?.state ?? 'UNKNOWN'} className={load.served ? 'is-on' : 'is-off'} title={`${load.watts} W modeled · ${loadEdge(room.id, load.id)?.reason ?? load.reason}`}><i />{load.name}<b>{status(room.id, load)}</b></span>)}</div></article>)}
    </div>
    <p className="power-map__footnote">{EDGE_FOOTNOTE}</p>
  </section>;
}
