with open('backend/app/schemas/snapshot.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('from typing import List', 'from typing import List, Any')

with open('backend/app/schemas/snapshot.py', 'w', encoding='utf-8') as f:
    f.write(text)
