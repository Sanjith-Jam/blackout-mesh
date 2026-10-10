import fs from 'fs';
let text = fs.readFileSync('backend/tests/test_electrical.py', 'utf8');

text = text.replace(/'load_a_w': True/g, "'loads_w': {'A': True}");
text = text.replace(/'load_b_w': -1/g, "'loads_w': {'B': -1}");

fs.writeFileSync('backend/tests/test_electrical.py', text);
