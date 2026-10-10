import re

with open('src/pages/DemoDashboard.tsx', 'r', encoding='utf-8') as f:
    dash = f.read()

# Fix 'zones.classroom' errors
dash = dash.replace('zones.classroom.active_classroom_id', '(zones?.classroom as any)?.active_classroom_id')
dash = dash.replace('zones?.classroom.classrooms', '(zones?.classroom as any)?.classrooms')
dash = dash.replace('cr => {', '(cr: any) => {')

with open('src/pages/DemoDashboard.tsx', 'w', encoding='utf-8') as f:
    f.write(dash)
