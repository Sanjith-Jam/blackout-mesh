import fs from 'fs';
let snapshot = fs.readFileSync('backend/app/schemas/snapshot.py', 'utf8');

// Remove HospitalRoom, ClassroomInfo, HospitalZone, ClassroomZone, FacilityZones
snapshot = snapshot.replace(/class HospitalRoom\(BaseModel\):[^]*?class FacilityZones\(BaseModel\):[^]*?classroom: ClassroomZone\r?\n/m, '');

// In SystemSnapshot, replace zones: FacilityZones with zones: Dict[str, Any]
snapshot = snapshot.replace(/zones: FacilityZones/, 'zones: Dict[str, Any]');

fs.writeFileSync('backend/app/schemas/snapshot.py', snapshot);

let state = fs.readFileSync('backend/app/core/state.py', 'utf8');
state = state.replace(/FacilityZones, HospitalZone, HospitalRoom,\s*ClassroomZone, ClassroomInfo, /, '');

state = state.replace(/zones = FacilityZones\([\s\S]*?classroom=ClassroomZone\([\s\S]*?classrooms=classroom_infos\n\s*\)\n\s*\)/m, zones = {
                'hospital': {'rooms': [c.model_dump() if hasattr(c, 'model_dump') else c for c in hospital_rooms]},
                'classroom': {
                    'active_classroom_id': next(iter(self.active_sessions.keys()), None) if self.active_sessions else None,
                    'recent_rfid_scan': None,
                    'rfid_reader_status': 'NOT_CONNECTED',
                    'classrooms': [c.model_dump() if hasattr(c, 'model_dump') else c for c in classroom_infos]
                }
            });

fs.writeFileSync('backend/app/core/state.py', state);
