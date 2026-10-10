import sys
import re

# 1. Update snapshot.py
with open('backend/app/schemas/snapshot.py', 'r', encoding='utf-8') as f:
    snapshot = f.read()

snapshot = re.sub(r'class HospitalRoom\(BaseModel\):[\s\S]*?class FacilityZones\(BaseModel\):[\s\S]*?classroom: ClassroomZone\r?\n', '', snapshot)
snapshot = snapshot.replace('zones: FacilityZones', 'zones: Dict[str, Any]')

# Add typing import for Dict, Any if needed
if 'Dict' not in snapshot:
    snapshot = snapshot.replace('from typing import ', 'from typing import Dict, Any, ')

with open('backend/app/schemas/snapshot.py', 'w', encoding='utf-8') as f:
    f.write(snapshot)

# 2. Update state.py
with open('backend/app/core/state.py', 'r', encoding='utf-8') as f:
    state = f.read()

state = state.replace('FacilityZones, HospitalZone, HospitalRoom,\n    ClassroomZone, ClassroomInfo, ', '')
state = state.replace('FacilityZones, HospitalZone, HospitalRoom, ClassroomZone, ClassroomInfo, ', '')

replacement = """            zones = {
                'hospital': {'rooms': [c.model_dump() if hasattr(c, 'model_dump') else c for c in hospital_rooms]},
                'classroom': {
                    'active_classroom_id': next(iter(self.active_sessions.keys()), None) if self.active_sessions else None,
                    'recent_rfid_scan': None,
                    'rfid_reader_status': 'NOT_CONNECTED',
                    'classrooms': [c.model_dump() if hasattr(c, 'model_dump') else c for c in classroom_infos]
                }
            }"""

state = re.sub(r'zones = FacilityZones\([\s\S]*?classroom=ClassroomZone\([\s\S]*?classrooms=classroom_infos\n\s*\)\n\s*\)', replacement, state)

with open('backend/app/core/state.py', 'w', encoding='utf-8') as f:
    f.write(state)

