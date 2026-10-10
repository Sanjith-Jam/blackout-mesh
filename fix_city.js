
const fs = require("fs");
let text = fs.readFileSync("frontend/src/pages/CityDemo.tsx", "utf8");

text = text.replace(/id === .A. \? .Hospital power state. : .Classroom power state./g, "`Feeder ${id} power state`");
text = text.replace(/title: `Feeder \$\{id\}.*?`/g, "title: `Feeder ${id}`");
text = text.replace(/changeCapacity\(6000\)/g, "changeCapacity(Math.round((snapshot.source.max_capacity_w ?? 14000) * 0.43))");
text = text.replace(/.6,000 W shortage applied. Protected demand takes priority../g, "`\${Math.round((snapshot.source.max_capacity_w ?? 14000) * 0.43).toLocaleString()} W shortage applied. Protected demand takes priority.`");
text = text.replace(/changeCapacity\(14000\)/g, "changeCapacity(snapshot.source.max_capacity_w ?? 14000)");
text = text.replace(/.14,000 W supply restored. Loads still wait for stable evidence../g, "`\${(snapshot.source.max_capacity_w ?? 14000).toLocaleString()} W supply restored. Loads still wait for stable evidence.`");
text = text.replace(/snapshot\.source\.capacity_w < 14000/g, "snapshot.source.capacity_w < (snapshot.source.max_capacity_w ?? 14000)");
text = text.replace(/Restore 14 kW supply/g, "Restore supply");

fs.writeFileSync("frontend/src/pages/CityDemo.tsx", text);

