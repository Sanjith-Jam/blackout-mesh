
import fs from "fs";

let classroom = fs.readFileSync("frontend/src/pages/ClassroomBlueprint.tsx", "utf8");
classroom = classroom.replace(/viewBox="0 0 1080 460"/g, "viewBox={`0 0 ${Math.max(1080, snapshot.rooms.length * 350 + 60)} 460`}");
classroom = classroom.replace(/<rect width="1080"/g, "<rect width={Math.max(1080, snapshot.rooms.length * 350 + 60)}");
classroom = classroom.replace(/"M150 408H1040"/g, "`M150 408H${Math.max(1080, snapshot.rooms.length * 350 + 60) - 40}`");
fs.writeFileSync("frontend/src/pages/ClassroomBlueprint.tsx", classroom);

let hospital = fs.readFileSync("frontend/src/pages/HospitalBlueprint.tsx", "utf8");
hospital = hospital.replace(/viewBox="0 0 1080 540"/g, "viewBox={`0 0 ${Math.max(1080, snapshot.transformers.length * 350 + 60)} 540`}");
hospital = hospital.replace(/<rect width="1080"/g, "<rect width={Math.max(1080, snapshot.transformers.length * 350 + 60)}");
hospital = hospital.replace(/"M150 465H1040"/g, "`M150 465H${Math.max(1080, snapshot.transformers.length * 350 + 60) - 40}`");
fs.writeFileSync("frontend/src/pages/HospitalBlueprint.tsx", hospital);

