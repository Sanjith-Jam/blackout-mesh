import re

with open('backend/app/schemas/snapshot.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'zones: Optional\[FacilityZones\] = None', 'zones: Optional[Dict[str, Any]] = None', text)

with open('backend/app/schemas/snapshot.py', 'w', encoding='utf-8') as f:
    f.write(text)
