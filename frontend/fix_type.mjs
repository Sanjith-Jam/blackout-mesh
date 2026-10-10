
import fs from "fs";

let text = fs.readFileSync("frontend/src/pages/ClassroomBlueprint.tsx", "utf8");
text = text.replace(/const on = \(id\) =>/g, "const on = (id: string) =>");
fs.writeFileSync("frontend/src/pages/ClassroomBlueprint.tsx", text);

