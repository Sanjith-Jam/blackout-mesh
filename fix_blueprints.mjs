
import fs from "fs";

let classroom = fs.readFileSync("frontend/src/pages/ClassroomBlueprint.tsx", "utf8");

classroom = classroom.replace(/\{snapshot\.rooms\.map\(\(room, index\) => \{[^]*?(?=<g transform="translate\(25 380\)")/g, `{snapshot.rooms.map((room, index) => {
          const x = 30 + index * 350;
          const on = (id) => loadEdge(room.id, id)?.state === "ENERGIZED";
          return <g key={room.id} data-room={room.id}>
            <rect x={x + 4} y="51" width="320" height="280" fill="#c6c6bc" />
            <rect x={x} y="46" width="320" height="280" fill="url(#classroom-tiles)" stroke="#747c76" strokeWidth="8" />
            <path d={\`M\${x + 104} 46h80M\${x + 320} 106v65\`} stroke="#a4c7cf" strokeWidth="7" />
            <path d={\`M\${x + 14} 326h40\`} stroke="#edece5" strokeWidth="12" />
            <path d={\`M\${x + 14} 326v-35h36\`} fill="none" stroke="#9e8b6c" strokeWidth="4" />
            <rect x={x + 120} y="56" width="90" height="12" fill="#52786a" stroke="#365346" strokeWidth="2" />
            <text x={x + 12} y="72" className="power-map__room-name">{room.id}</text>
            <text x={x + 12} y="88" className="power-map__map-note">{room.rfid_active ? "RFID ACTIVE" : "NO RECENT SCAN"}</text>
            {wire(\`classroom:BUS>\${room.id}\`, \`M\${x + 32} 408V96\`, true)}
            {room.loads.map((load, lIdx) => {
              const isOn = on(load.id);
              const lx = x + 80 + (lIdx % 2) * 120;
              const ly = 100 + Math.floor(lIdx / 2) * 60;
              return <g key={load.id} transform={\`translate(\${lx} \${ly})\`}>
                {wire(\`classroom:\${room.id}>\${load.id}\`, \`M\${x + 32} \${ly}H\${lx - 30}\`)}
                <rect x="-30" y="-15" width="70" height="30" fill={isOn ? "#68b6c2" : "#a6aaa2"} stroke={isOn ? "#3c585b" : "#797762"} strokeWidth="2" rx="4" />
                <text y="4" textAnchor="middle" fill="#fff" fontSize="10" fontWeight="bold" style={{textTransform: "uppercase"}}>{load.name.substring(0, 10)}</text>
              </g>;
            })}
            <rect x={x + 20} y="282" width="24" height="29" fill="#e1c971" stroke="#8e7d40" strokeWidth="2" />
            <path d={\`m\${x + 34} 286-9 12h7l-4 9 12-14h-7Z\`} fill="#82632b" />
            <g transform={\`translate(\${x + 65} 318)\`}><rect x="-7" y="-10" width="14" height="20" fill={room.rfid_active ? "#6abca0" : "#a2aaa1"} stroke="#5f7569" strokeWidth="2" /><circle r="2" fill={room.rfid_active ? "#d9fff0" : "#d0d4cb"} /></g>
            <text x={x + 80} y="363" className="power-map__feed-label">{room.loads.filter(load => load.served).reduce((sum, load) => sum + load.watts, 0).toLocaleString()} W MODELED / {room.rfid_active ? "ACTIVE ROOM" : "ESSENTIALS FIRST"}</text>
          </g>;
        })}
        `);
fs.writeFileSync("frontend/src/pages/ClassroomBlueprint.tsx", classroom);

let hospital = fs.readFileSync("frontend/src/pages/HospitalBlueprint.tsx", "utf8");
hospital = hospital.replace(/const zones: \{[^]*?\]\}\];/, "");

hospital = hospital.replace(/\{zones\.map\(\(z, index\) => \{[^]*?(?=<g transform="translate\(25 436\)")/g, `{snapshot.transformers.map((tx, index) => {
          const x = 30 + index * 350;
          const txId = tx.id;
          const severity = tx.diagnosis.severity ?? "unknown";
          const energized = tx.energized;
          const current = tx.sensors.current_a;
          const temp = tx.sensors.temperature_c;
          const outputV = tx.sensors.output_voltage_v;
          const coolingOk = tx.sensors.cooling_ok;

          return <g key={txId}>
            <rect x={x + 4} y="51" width="320" height="310" fill="#c6c6bc" />
            <rect x={x} y="46" width="320" height="310" fill="url(#zone-tiles)" stroke={severity === "normal" ? "#5a7a5e" : severity === "high" || severity === "critical" ? "#9c4444" : severity === "medium" ? "#8a7530" : "#6b7280"} strokeWidth="8" />
            <rect x={x + 120} y="56" width="90" height="12" fill={severity === "normal" ? "#52786a" : severity === "high" || severity === "critical" ? "#8b3838" : severity === "medium" ? "#7a6520" : "#5a6370"} stroke={severity === "normal" ? "#365346" : "#444"} strokeWidth="2" />
            <text x={x + 12} y="72" className="power-map__room-name">{tx.zone}</text>
            <text x={x + 12} y="88" className="power-map__map-note">{tx.diagnosis.code.replace(/_/g, " ")}</text>
            <rect x={x + 240} y="62" width="68" height="48" rx="4" fill={energized ? "#4a6e50" : "#6b6b6b"} stroke={energized ? "#2d4a32" : "#444"} strokeWidth="2" />
            <text x={x + 274} y="80" textAnchor="middle" fill="#e8f0ea" style={{ fontSize: "8px", fontWeight: 800, fontFamily: "ui-monospace, monospace" }}>{tx.id}</text>
            <text x={x + 274} y="96" textAnchor="middle" fill="#c4daca" style={{ fontSize: "6px", fontWeight: 600, fontFamily: "ui-monospace, monospace" }}>{current != null ? \`\${current.toFixed(0)}A\` : "—"} / {temp != null ? \`\${temp.toFixed(0)}°C\` : "—"}</text>
            <text x={x + 274} y="106" textAnchor="middle" fill="#c4daca" style={{ fontSize: "5px", fontWeight: 700, fontFamily: "ui-monospace, monospace" }}>SIM SENSOR</text>

            {wire(\`hospital:BUS>\${txId}\`, \`M\${x + 32} 465V106\`, true)}
            
            {tx.loads.map((load, lIdx) => {
              const e = edges[\`hospital:\${txId}>\${load.id}\`];
              const isOn = e?.state === "ENERGIZED";
              const lx = x + 80 + (lIdx % 2) * 120;
              const ly = 130 + Math.floor(lIdx / 2) * 60;
              return <g key={load.id} transform={\`translate(\${lx} \${ly})\`}>
                {wire(\`hospital:\${txId}>\${load.id}\`, \`M\${x + 32} \${ly}H\${lx - 30}\`)}
                <rect x="-30" y="-15" width="70" height="30" fill={isOn ? "#68b6c2" : "#a6aaa2"} stroke={isOn ? "#3c585b" : "#797762"} strokeWidth="2" rx="4" />
                <text y="4" textAnchor="middle" fill="#fff" fontSize="10" fontWeight="bold" style={{textTransform: "uppercase"}}>{(load.name || load.id).substring(0, 10)}</text>
              </g>;
            })}

            <g transform={\`translate(\${x + 65} 340)\`}>
              <rect x="-7" y="-10" width="14" height="20" fill={coolingOk ? "#6abca0" : coolingOk === false ? "#c45c5c" : "#a2aaa1"} stroke="#5f7569" strokeWidth="2" />
              <circle r="2" fill={coolingOk ? "#d9fff0" : coolingOk === false ? "#ffd0d0" : "#d0d4cb"} />
            </g>
            <rect x={x + 20} y="300" width="24" height="29" fill="#e1c971" stroke="#8e7d40" strokeWidth="2" />
            <path d={\`m\${x + 34} 304-9 12h7l-4 9 12-14h-7Z\`} fill="#82632b" />
            <text x={x + 80} y="380" className="power-map__feed-label">{outputV != null ? \`\${outputV.toFixed(0)} V SIM SENSOR\` : "— V (NO READING)"} / {severity === "normal" ? "ALL SYSTEMS" : severity.toUpperCase()}</text>
          </g>;
        })}
        `);
        
hospital = hospital.replace(/\{zones\.map\(\(z\) => \{[^]*?\)\}\}/, `{snapshot.transformers.map((tx) => {
        const txId = tx.id;
        const severity = tx.diagnosis.severity ?? "unknown";
        return <article key={tx.zone} className={severity !== "normal" && severity !== "unknown" ? "is-selected" : ""} aria-label={\`\${tx.zone} equipment status\`}>
          <header><strong>{tx.zone}</strong><span>{tx.diagnosis.code.replace(/_/g, " ")}</span></header>
          <div className="power-map__loads">
            {tx.loads.map(eq => {
              const e = edges[\`hospital:\${txId}>\${eq.id}\`];
              const state = e?.state ?? "UNKNOWN";
              return <span key={eq.id} data-edge-state={state} className={state === "ENERGIZED" ? "is-on" : "is-off"} title={\`\${eq.name || eq.id} — \${e?.reason ?? "no edge data"}\`}>
                <i />{eq.name || eq.id}<b>{EDGE_LABEL[state]}</b>
              </span>
            })}
            <span className={tx.sensors.cooling_ok ? "is-on" : "is-off"} title="Cooling system">
              <i />Cooling<b>{tx.sensors.cooling_ok == null ? "—" : tx.sensors.cooling_ok ? "OK" : "FAIL"}</b>
            </span>
          </div>
        </article>;
      })}`);

fs.writeFileSync("frontend/src/pages/HospitalBlueprint.tsx", hospital);

