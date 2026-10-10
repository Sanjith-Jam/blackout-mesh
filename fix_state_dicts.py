with open('backend/app/core/state.py', 'r', encoding='utf-8') as f:
    state = f.read()

state = state.replace('HospitalRoom(id=r["id"], name=r["name"], lighting_service=r["lighting_service"], led_bit=r["led_bit"])', '{"id": r["id"], "name": r["name"], "lighting_service_id": r["lighting_service"], "led_bit": r["led_bit"]}')
state = state.replace('ClassroomInfo(', 'dict(')
with open('backend/app/core/state.py', 'w', encoding='utf-8') as f:
    f.write(state)
