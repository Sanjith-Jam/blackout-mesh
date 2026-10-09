import os

with open('frontend/src/pages/DemoDashboard.tsx', 'r') as f:
    dashboard = f.read()

new_dashboard = dashboard.replace(
    'export default function DemoDashboard() {',
    'export default function DemoDashboard() {\n  const [activeTab, setActiveTab] = useState("overview");'
)

tabs_ui = """
      <div className="demo-tabs" style={{ display: 'flex', gap: '1rem', padding: '0 2rem', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')} style={{ padding: '1rem', border: 'none', background: 'none', borderBottom: activeTab === 'overview' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600 }}>System Overview</button>
        <button className={`tab-btn ${activeTab === 'hospital' ? 'active' : ''}`} onClick={() => setActiveTab('hospital')} style={{ padding: '1rem', border: 'none', background: 'none', borderBottom: activeTab === 'hospital' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600 }}>Hospital Zone</button>
        <button className={`tab-btn ${activeTab === 'classrooms' ? 'active' : ''}`} onClick={() => setActiveTab('classrooms')} style={{ padding: '1rem', border: 'none', background: 'none', borderBottom: activeTab === 'classrooms' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600 }}>Classroom Zone</button>
      </div>
"""

new_dashboard = new_dashboard.replace(
    '<div className="demo-content">',
    tabs_ui + '\n      <div className="demo-content">'
)

new_dashboard = new_dashboard.replace(
    '<div className="charts-row">',
    '{activeTab === "overview" && <div className="charts-row">'
)
new_dashboard = new_dashboard.replace(
    '<AllocationHistoryChart history={history} />\n            </div>',
    '<AllocationHistoryChart history={history} />\n            </div>}'
)

new_dashboard = new_dashboard.replace(
    '<section className="zone-section">\n            <div className="zone-header">\n              <h2>Network Topology</h2>',
    '{activeTab === "overview" && <section className="zone-section">\n            <div className="zone-header">\n              <h2>Network Topology</h2>'
)
new_dashboard = new_dashboard.replace(
    '<TopologyGraph snapshot={snapshot} />\n          </section>',
    '<TopologyGraph snapshot={snapshot} />\n          </section>}'
)

new_dashboard = new_dashboard.replace(
    '{/* HOSPITAL ZONE */}\n          <section className="zone-section">',
    '{/* HOSPITAL ZONE */}\n          {activeTab === "hospital" && <section className="zone-section">'
)
new_dashboard = new_dashboard.replace(
    '</div>\n              ))}\n            </div>\n          </section>',
    '</div>\n              ))}\n            </div>\n          </section>}'
)
new_dashboard = new_dashboard.replace(
    '</div>\n              ))} \n            </div>\n          </section>',
    '</div>\n              ))} \n            </div>\n          </section>}'
)


new_dashboard = new_dashboard.replace(
    '{/* CLASSROOM ZONE */}\n          <section className="zone-section">\n            <div className="zone-header">\n              <h2>RFID Classroom Zone</h2>',
    '{/* CLASSROOM ZONE */}\n          {activeTab === "classrooms" && <section className="zone-section">\n            <div className="zone-header">\n              <h2>RFID Classroom Zone</h2>'
)

new_dashboard = new_dashboard.replace(
    '</div>\n                  </div>\n                );\n              })}\n            </div>\n          </section>',
    '</div>\n                  </div>\n                );\n              })}\n            </div>\n          </section>}'
)


with open('frontend/src/pages/DemoDashboard.tsx', 'w') as f:
    f.write(new_dashboard)
