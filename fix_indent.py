with open('backend/app/core/state.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('                        zones = {', '            zones = {')
with open('backend/app/core/state.py', 'w', encoding='utf-8') as f:
    f.write(text)
