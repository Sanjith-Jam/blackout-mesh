import re

with open('src/pages/CityDemo.tsx', 'r', encoding='utf-8') as f:
    city = f.read()

city = city.replace('(snapshot.zones?.classroom?.classrooms || [])', '((snapshot.zones?.classroom as any)?.classrooms || [])')

with open('src/pages/CityDemo.tsx', 'w', encoding='utf-8') as f:
    f.write(city)
