with open('frontend/src/pages/DemoDashboard.tsx', 'r') as f:
    content = f.read()

tabs_ui = """
      <div className="demo-tabs" style={{ display: 'flex', gap: '1rem', padding: '0 0', borderBottom: '1px solid #e2e8f0', background: 'transparent', marginBottom: '1.5rem' }}>
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')} style={{ padding: '0.75rem 1.5rem', border: 'none', background: 'none', borderBottom: activeTab === 'overview' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600, fontSize: '1rem' }}>Overview</button>
        <button className={`tab-btn ${activeTab === 'hospital' ? 'active' : ''}`} onClick={() => setActiveTab('hospital')} style={{ padding: '0.75rem 1.5rem', border: 'none', background: 'none', borderBottom: activeTab === 'hospital' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600, fontSize: '1rem' }}>Hospital Zone</button>
        <button className={`tab-btn ${activeTab === 'classrooms' ? 'active' : ''}`} onClick={() => setActiveTab('classrooms')} style={{ padding: '0.75rem 1.5rem', border: 'none', background: 'none', borderBottom: activeTab === 'classrooms' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600, fontSize: '1rem' }}>Classroom Zone</button>
      </div>
"""

content = content.replace(
    '<div className="zones-layout">',
    tabs_ui + '\n      <div className="zones-layout">'
)

with open('frontend/src/pages/DemoDashboard.tsx', 'w') as f:
    f.write(content)
