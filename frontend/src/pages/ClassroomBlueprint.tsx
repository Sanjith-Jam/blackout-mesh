import { ClassroomDemoRoom } from '../types';
import './ClassroomBlueprint.css';

type Props = { room: ClassroomDemoRoom; selected: boolean; energized: boolean };

export default function ClassroomBlueprint({ room, selected, energized }: Props) {
  const load = (id: string) => room.loads.find(item => item.id === id);
  const lights = load('lighting');
  const computers = load('computers');
  const fans = load('fans');
  const projector = load('projector');
  const ac = load('ac');
  const instruments = load('instruments');
  const stateClass = (served?: boolean) => served ? 'is-served' : 'is-shed';
  const conduit = (d: string, served?: boolean) => <path d={d} className={`blueprint__wire ${stateClass(served)} ${energized && served ? 'is-live' : ''}`} />;
  const deskRows = [0, 1, 2].map(row => (room.id === 'CR3' ? [0, 1, 2] : [0, 1, 2, 3]).map(col => {
    const x = 308 + col * 146;
    const y = 166 + row * 54;
    return <g key={`${row}-${col}`} className={`blueprint__computer ${stateClass(computers?.served)}`}>
      <rect x={x} y={y} width="104" height="34" rx="3" />
      <rect className="blueprint__screen" x={x + 35} y={y + 4} width="27" height="18" rx="2" />
      <path d={`M${x + 48} ${y + 22}v4m-7 0h14`} />
      <rect className="blueprint__keyboard" x={x + 68} y={y + 22} width="23" height="5" rx="1" />
      <circle className="blueprint__chair" cx={x + 51} cy={y + 42} r="7" />
    </g>;
  }));

  return <article className={`blueprint ${selected ? 'blueprint--selected' : ''} ${energized ? '' : 'blueprint--paused'}`} aria-labelledby={`${room.id}-blueprint-title`}>
    <div className="blueprint__heading">
      <div><span className="blueprint__eyebrow">Overhead electrical plan · simulated</span><h3 id={`${room.id}-blueprint-title`}>{room.name}</h3></div>
      <div className={`blueprint__room-state ${selected ? 'is-selected' : ''}`}><span className="blueprint__status-dot" />{selected ? 'RFID entry selected' : room.rfid_active ? 'RFID session active' : 'Standby'}</div>
    </div>
    <div className="blueprint__drawing-wrap">
      <svg className="blueprint__drawing" viewBox="0 0 1160 410" role="img" aria-label={`${room.name} overhead floor plan. ${room.loads.map(item => `${item.name} ${item.served ? 'on' : 'off'}, ${item.watts} watts`).join('. ')}.`}>
        <defs>
          <pattern id={`${room.id}-grid`} width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#817d70" strokeOpacity=".11" strokeWidth=".7" /></pattern>
          <radialGradient id={`${room.id}-light-pool`}><stop stopColor="#ffe08a" stopOpacity=".58" /><stop offset="1" stopColor="#ffe08a" stopOpacity="0" /></radialGradient>
          <filter id={`${room.id}-glow`} x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <rect width="1160" height="410" fill={`url(#${room.id}-grid)`} />
        {/* perimeter walls, with a doorway on the south side and two glazed windows */}
        <path className="blueprint__wall" d="M70 72H278m90 0h277m90 0h305M70 72v258m0 22v24h53m100 0h882v-24m0-22V72" />
        <path className="blueprint__window" d="M278 67v10m90-10v10m277-10v10m90-10v10m305-10v10" />
        <path className="blueprint__window-line" d="M278 72h90m277 0h90m305 0h78" />
        {/* entrance opening, door leaf and swing arc */}
        <path className="blueprint__door" d="M123 376v-100m0 100a100 100 0 0 1 100-100" />
        <text className="blueprint__tiny-label" x="128" y="393">ENTRY</text>
        {/* front teaching wall and board */}
        <rect className="blueprint__board" x="394" y="82" width="410" height="18" rx="2" />
        <path className="blueprint__board-line" d="M406 91h210m220 0h26" />
        <text className="blueprint__label" x="574" y="116" textAnchor="middle">TEACHING BOARD</text>
        {/* electrical subpanel and wall conduit trunk */}
        <rect className="blueprint__panel-box" x="88" y="112" width="48" height="63" rx="3" />
        <text className="blueprint__panel-title" x="112" y="132" textAnchor="middle">DB</text>
        <path className="blueprint__panel-mark" d="m113 138-8 13h8l-3 10 10-14h-8z" />
        <text className="blueprint__micro-label" x="112" y="187" textAnchor="middle">ROOM PANEL</text>
        {conduit('M136 143H173V108H1080V346H158V175', true)}
        {/* branch conduits follow the ceiling/perimeter before dropping to each fixture */}
        {conduit('M285 108V144M488 108V144M691 108V144M894 108V144M285 108H1080', lights?.served)}
        {conduit('M386 108V128H822V108', fans?.served)}
        {conduit('M1080 196H1037', ac?.served)}
        {conduit('M490 108V126H610V111', projector?.served)}
        {room.id === 'CR3' && conduit('M158 346V311H1015V304', instruments?.served)}
        {conduit('M165 346H281V183M281 183H905M281 237H905M281 291H905M281 183V291', computers?.served)}
        {/* lighting pools and ceiling fixtures */}
        {[285, 488, 691, 894].map((x, i) => <g key={x} className={stateClass(lights?.served)}>
          {lights?.served && <ellipse className="blueprint__light-pool" cx={x} cy="224" rx="130" ry="108" fill={`url(#${room.id}-light-pool)`} />}
          <rect className="blueprint__fixture blueprint__light" x={x - 29} y="134" width="58" height="12" rx="5" />
          <text className="blueprint__micro-label" x={x} y="129" textAnchor="middle">L{i + 1}</text>
        </g>)}
        {/* projector suspended over the teaching area */}
        <g className={`blueprint__device ${stateClass(projector?.served)}`}>
          <path className="blueprint__mount" d="M610 108v22" /><rect x="592" y="130" width="36" height="24" rx="4" />
          <circle className="blueprint__lens" cx="610" cy="142" r="4" />
          {projector?.served && <path className="blueprint__projection" d="M605 130 541 101H679L615 130Z" />}
          <text className="blueprint__label" x="610" y="173" textAnchor="middle">PROJECTOR · {projector?.watts ?? 0} W</text>
        </g>
        {/* four ceiling fans */}
        {[386, 532, 678, 824].map((x, i) => <g key={x} className={`blueprint__fan ${stateClass(fans?.served)}`} transform={`translate(${x} 146)`}>
          <circle className="blueprint__fan-hub" r="6" />
          <g className={energized && fans?.served ? 'blueprint__fan-blades is-turning' : 'blueprint__fan-blades'}>
            <path d="M0-5c-5-16-2-32 3-35 8 12 8 23 4 37M5 0c16-5 32-2 35 3C28 11 17 11 3 5M0 5c5 16 2 32-3 35C-11 28-11 17-5 3M-5 0c-16 5-32 2-35-3C-28-11-17-11-3-5" />
          </g>
          <text className="blueprint__micro-label" x="0" y="51" textAnchor="middle">F{i + 1}</text>
        </g>)}
        {/* three rows of computer desks */}
        {deskRows}
        <text className="blueprint__label" x="585" y="350" textAnchor="middle">COMPUTER DESKS · {computers?.watts ?? 0} W TOTAL</text>
        {/* wall mounted AC with airflow */}
        <g className={`blueprint__device ${stateClass(ac?.served)}`}>
          <rect x="1038" y="160" width="72" height="38" rx="5" />
          <path className="blueprint__vent" d="M1048 188h52m-47-8h42" />
          {ac?.served && <path className="blueprint__air" d="M1043 203q-24 17 0 30t0 29m19-59q-24 17 0 30t0 29m19-59q-24 17 0 30t0 29" />}
          <text className="blueprint__label" x="1074" y="151" textAnchor="middle">WALL AC</text>
          <text className="blueprint__micro-label" x="1074" y="218" textAnchor="middle">{ac?.watts ?? 0} W</text>
        </g>
        {/* CR3 instrument benches */}
        {room.id === 'CR3' && <g className={`blueprint__device ${stateClass(instruments?.served)}`}>
          {[0, 1, 2].map(i => <g key={i} transform={`translate(${884 + i * 74} 258)`}>
            <rect className="blueprint__bench" width="62" height="46" rx="3" />
            <rect className="blueprint__scope" x="8" y="8" width="23" height="19" rx="2" />
            <path className="blueprint__trace" d="M11 19h4l4-7 4 12 4-8h3" />
            <circle className="blueprint__knob" cx="46" cy="14" r="4" />
            <text className="blueprint__micro-label" x="31" y="41" textAnchor="middle">SCOPE</text>
          </g>)}
          <text className="blueprint__label" x="976" y="325" textAnchor="middle">LAB INSTRUMENTS · {instruments?.watts ?? 0} W</text>
        </g>}
        {/* entry reader is the visual RFID selection point */}
        <g className={`blueprint__reader ${selected ? 'is-active' : ''}`} transform="translate(157 291)">
          <rect width="25" height="32" rx="4" />
          <circle cx="12.5" cy="10" r="3" />
          <path d="M7 17q5-5 11 0m-14 4q8-8 16 0" />
          <text className="blueprint__micro-label" x="12" y="45" textAnchor="middle">RFID</text>
        </g>
        {/* load state and served wattage legend */}
        <g className={`blueprint__tag ${lights?.served ? 'is-served' : 'is-shed'}`} transform="translate(208 120)"><circle r="5" /><text x="10" y="4">LIGHTS · {lights?.watts ?? 0} W · {lights?.served ? 'ON' : 'OFF'}</text></g>
        <g className={`blueprint__tag ${computers?.served ? 'is-served' : 'is-shed'}`} transform="translate(208 142)"><circle r="5" /><text x="10" y="4">COMPUTERS · {computers?.watts ?? 0} W · {computers?.served ? 'ON' : 'OFF'}</text></g>
        <g className={`blueprint__tag ${fans?.served ? 'is-served' : 'is-shed'}`} transform="translate(208 164)"><circle r="5" /><text x="10" y="4">FANS · {fans?.watts ?? 0} W · {fans?.served ? 'ON' : 'OFF'}</text></g>
      </svg>
    </div>
    <div className="blueprint__load-list" aria-label={`${room.name} equipment status`}>
      {room.loads.map(item => <div key={item.id} className={`blueprint__load ${item.served ? 'is-served' : 'is-shed'}`}>
        <span className="blueprint__status-dot" /><span className="blueprint__load-name">{item.name}</span>
        <strong>{item.watts.toLocaleString()} W</strong><b>{item.served ? 'ON' : /restor/i.test(item.reason) ? 'RESTORING' : 'OFF'}</b>
        {!item.served && <span className="blueprint__load-reason">{item.reason}</span>}
      </div>)}
    </div>
  </article>;
}
