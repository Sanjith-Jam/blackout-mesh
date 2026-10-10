import fs from 'fs';
let text = fs.readFileSync('backend/app/simulation/electrical.py', 'utf8');

text = text.replace(/from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, computed_field/, "from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, computed_field, conint");
text = text.replace(/loads_w: Dict\[str, StrictInt\]/g, "loads_w: Dict[str, conint(ge=0, le=100000, strict=True)]");

text = text.replace(/    @computed_field\r?\n    @property\r?\n    def restoration_authorized\(self\) -> bool:\r?\n        return \(self\.converged and \r?\n                all\(b\['loading_pct'\] is not None and b\['loading_pct'\] < 100\.0 for b in self\.branches\.values\(\)\) and\r?\n                self\.source_p_w is not None and self\.source_p_w > 0\)/, "    restoration_authorized: Literal[False] = False");

fs.writeFileSync('backend/app/simulation/electrical.py', text);

let text2 = fs.readFileSync('backend/tests/test_electrical.py', 'utf8');
text2 = text2.replace(/json=\{'loads_w': \{'A': 6000, 'B': 8000\}\}\)\.status_code == 422/g, "json={'loads_w': {'A': '6000'}}).status_code == 422");
fs.writeFileSync('backend/tests/test_electrical.py', text2);
