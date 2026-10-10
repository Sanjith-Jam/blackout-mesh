import re
with open('backend/app/core/state.py', 'r', encoding='utf-8') as f:
    state = f.read()

state = re.sub(r'HospitalRoom\([^)]+\)', '{"id": r["id"], "name": r["name"], "lighting_service_id": r["lighting_service"], "led_bit": r["led_bit"]}', state)
state = re.sub(r'ClassroomInfo\(', 'dict(', state)

with open('backend/app/core/state.py', 'w', encoding='utf-8') as f:
    f.write(state)
