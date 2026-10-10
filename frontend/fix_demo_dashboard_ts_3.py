import re

with open('src/pages/DemoDashboard.tsx', 'r', encoding='utf-8') as f:
    dash = f.read()

dash = dash.replace('zones[zone].active_classroom_id', '(zones[zone] as any).active_classroom_id')
dash = dash.replace('(zones[zone].rooms || zones[zone].classrooms || [])', '((zones[zone] as any).rooms || (zones[zone] as any).classrooms || [])')

with open('src/pages/DemoDashboard.tsx', 'w', encoding='utf-8') as f:
    f.write(dash)
