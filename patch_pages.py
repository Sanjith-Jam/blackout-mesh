import re

# PATCH HOSPITAL
with open('frontend/src/pages/HospitalDemo.tsx', 'r') as f:
    h = f.read()

h = h.replace('export default function DemoDashboard() {', 'export default function HospitalDemo() {')
h = re.sub(r'const \[activeTab.*?;\n', '', h)
h = re.sub(r'<div className="demo-tabs".*?</div>', '', h, flags=re.DOTALL)

# Keep only Hospital zone, remove activeTab checks
h = h.replace('{activeTab === "overview" && <div className="charts-row">', '<div className="charts-row" style={{display:"none"}}>')
h = h.replace('{activeTab === "overview" && <section className="zone-section">', '<section className="zone-section" style={{display:"none"}}>')
h = h.replace('{activeTab === "hospital" && <section className="zone-section">', '<section className="zone-section">')
h = h.replace('{activeTab === "classrooms" && <section className="zone-section">', '<section className="zone-section" style={{display:"none"}}>')
# Remove the extra closing braces
h = re.sub(r'</section>}', '</section>', h)
h = re.sub(r'</div>}', '</div>', h)

with open('frontend/src/pages/HospitalDemo.tsx', 'w') as f:
    f.write(h)

# PATCH CLASSROOMS
with open('frontend/src/pages/ClassroomsDemo.tsx', 'r') as f:
    c = f.read()

c = c.replace('export default function DemoDashboard() {', 'export default function ClassroomsDemo() {')
c = re.sub(r'const \[activeTab.*?;\n', '', c)
c = re.sub(r'<div className="demo-tabs".*?</div>', '', c, flags=re.DOTALL)

c = c.replace('{activeTab === "overview" && <div className="charts-row">', '<div className="charts-row" style={{display:"none"}}>')
c = c.replace('{activeTab === "overview" && <section className="zone-section">', '<section className="zone-section" style={{display:"none"}}>')
c = c.replace('{activeTab === "hospital" && <section className="zone-section">', '<section className="zone-section" style={{display:"none"}}>')
c = c.replace('{activeTab === "classrooms" && <section className="zone-section">', '<section className="zone-section">')
c = re.sub(r'</section>}', '</section>', c)
c = re.sub(r'</div>}', '</div>', c)

with open('frontend/src/pages/ClassroomsDemo.tsx', 'w') as f:
    f.write(c)
