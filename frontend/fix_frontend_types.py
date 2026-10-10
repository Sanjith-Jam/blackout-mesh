import re
with open('src/types.ts', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'export type HospitalRoom = components\[\'schemas\'\]\[\'HospitalRoom\'\];\r?\n', '', text)
text = re.sub(r'export type HospitalZone = components\[\'schemas\'\]\[\'HospitalZone\'\];\r?\n', '', text)
text = re.sub(r'export type ClassroomInfo = components\[\'schemas\'\]\[\'ClassroomInfo\'\];\r?\n', '', text)
text = re.sub(r'export type ClassroomZone = components\[\'schemas\'\]\[\'ClassroomZone\'\];\r?\n', '', text)
text = re.sub(r'export type FacilityZones = components\[\'schemas\'\]\[\'FacilityZones\'\];\r?\n', '', text)

with open('src/types.ts', 'w', encoding='utf-8') as f:
    f.write(text)

with open('src/pages/CityDemo.tsx', 'r', encoding='utf-8') as f:
    city = f.read()

city = city.replace('snapshot.zones?.classroom.classrooms', '(snapshot.zones?.classroom?.classrooms || [])')
with open('src/pages/CityDemo.tsx', 'w', encoding='utf-8') as f:
    f.write(city)

with open('src/pages/ClassroomBlueprint.tsx', 'r', encoding='utf-8') as f:
    cb = f.read()
cb = cb.replace('const on = (id) =>', 'const on = (id: string) =>')
with open('src/pages/ClassroomBlueprint.tsx', 'w', encoding='utf-8') as f:
    f.write(cb)
