import fs from 'fs';
let text = fs.readFileSync('backend/tests/test_electrical.py', 'utf8');

text = text.replace(/load_a_w=12000/g, "loads_w={'A': 12000, 'B': 8000}");
text = text.replace(/feeder_b_closed=False/g, "feeders_closed={'A': True, 'B': False}");
text = text.replace(/json=\{'load_a_w': '6000'\}/g, "json={'loads_w': {'A': 6000, 'B': 8000}}");

fs.writeFileSync('backend/tests/test_electrical.py', text);
