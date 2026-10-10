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
      <svg className="power-map__drawing" viewBox={`0 0 ${Math.max(1080, snapshot.rooms.length * 350 + 60)} 460`} role="img" aria-label={`Three classrooms connected to a shared simulated supply. ${snapshot.rooms.map(room => `${room.name}: ${room.loads.map(load => `${load.name} ${status(room.id, load)}`).join(', ')}`).join('. ')}`}>
        <defs>
          <pattern id="campus-tiles" width="20" height="20" patternUnits="userSpaceOnUse"><rect width="20" height="20" fill="#edece5" /><path d="M20 0H0V20" fill="none" stroke="#d9dad2" strokeWidth=".7" /></pattern>
          <pattern id="classroom-tiles" width="20" height="20" patternUnits="userSpaceOnUse"><rect width="20" height="20" fill="#f5efdd" /><path d="M20 0H0V20" fill="none" stroke="#e6dfcb" strokeWidth=".8" /></pattern>
        </defs>
        <rect width={Math.max(1080, snapshot.rooms.length * 350 + 60)} height="460" fill="url(#campus-tiles)" />
        <text x="30" y="26" className="power-map__map-note">CLASSROOM BLOCK / POWER DISTRIBUTION</text>
        {snapshot.rooms.map((room, index) => {
          const x = 30 + index * 350;
          const on = (id: string) => loadEdge(room.id, id)?.state === "ENERGIZED";
          return <g key={room.id} data-room={room.id}>
            <rect x={x + 4} y="51" width="320" height="280" fill="#c6c6bc" />
            <rect x={x} y="46" width="320" height="280" fill="url(#classroom-tiles)" stroke="#747c76" strokeWidth="8" />
            <path d={`M${x + 104} 46h80M${x + 320} 106v65`} stroke="#a4c7cf" strokeWidth="7" />
            <path d={`M${x + 14} 326h40`} stroke="#edece5" strokeWidth="12" />
            <path d={`M${x + 14} 326v-35h36`} fill="none" stroke="#9e8b6c" strokeWidth="4" />
            <rect x={x + 120} y="56" width="90" height="12" fill="#52786a" stroke="#365346" strokeWidth="2" />
            <text x={x + 12} y="72" className="power-map__room-name">{room.id}</text>
            <text x={x + 12} y="88" className="power-map__map-note">{room.rfid_active ? "RFID ACTIVE" : "NO RECENT SCAN"}</text>
            {wire(`classroom:BUS>${room.id}`, `M${x + 32} 408V96`, true)}
            {room.loads.map((load, lIdx) => {
              const isOn = on(load.id);
              const lx = x + 80 + (lIdx % 2) * 120;
              const ly = 100 + Math.floor(lIdx / 2) * 60;
              return <g key={load.id} transform={`translate(${lx} ${ly})`}>
                {wire(`classroom:${room.id}>${load.id}`, `M${x + 32} ${ly}H${lx - 30}`)}
                <rect x="-30" y="-15" width="70" height="30" fill={isOn ? "#68b6c2" : "#a6aaa2"} stroke={isOn ? "#3c585b" : "#797762"} strokeWidth="2" rx="4" />
                <text y="4" textAnchor="middle" fill="#fff" fontSize="10" fontWeight="bold" style={{textTransform: "uppercase"}}>{load.name.substring(0, 10)}</text>
              </g>;
            })}
            <rect x={x + 20} y="282" width="24" height="29" fill="#e1c971" stroke="#8e7d40" strokeWidth="2" />
            <path d={`m${x + 34} 286-9 12h7l-4 9 12-14h-7Z`} fill="#82632b" />
            <g transform={`translate(${x + 65} 318)`}><rect x="-7" y="-10" width="14" height="20" fill={room.rfid_active ? "#6abca0" : "#a2aaa1"} stroke="#5f7569" strokeWidth="2" /><circle r="2" fill={room.rfid_active ? "#d9fff0" : "#d0d4cb"} /></g>
            <text x={x + 80} y="363" className="power-map__feed-label">{room.loads.filter(load => load.served).reduce((sum, load) => sum + load.watts, 0).toLocaleString()} W MODELED / {room.rfid_active ? "ACTIVE ROOM" : "ESSENTIALS FIRST"}</text>
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
