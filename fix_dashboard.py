import re

with open('frontend/src/pages/DemoDashboard.tsx', 'r', encoding='utf-8') as f:
    dashboard = f.read()

# Replace tabs
dashboard = re.sub(
    r'<button className=\{\	ab-btn \$\{\(activeTab === \'classrooms\' \? \'active\' : \'\'\)\}\\} onClick=\{[^>]*>Classroom Zone</button>',
    r'''{Object.keys(zones || {}).map(zone => (
            <button key={zone} className={	ab-btn } onClick={() => setActiveTab(zone)} style={{ padding: '0.75rem 1.5rem', border: 'none', background: 'none', borderBottom: activeTab === zone ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600, fontSize: '1rem', textTransform: 'capitalize' }}>{zone} Zone</button>
          ))}''',
    dashboard
)
# Delete hospital tab
dashboard = re.sub(
    r'<button className=\{\	ab-btn \$\{\(activeTab === \'hospital\' \? \'active\' : \'\'\)\}\\} onClick=\{[^>]*>Hospital Zone</button>',
    '',
    dashboard
)

# Replace classroom content with generic
replacement = r'''{Object.keys(zones || {}).map(zone => activeTab === zone && (
            <section key={zone} className="zone-section">
              <div className="zone-cards" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
                {(zones[zone].rooms || zones[zone].classrooms || []).map((room: any) => {
                  const isSelected = zones[zone].active_classroom_id === room.id;
                  const svc = getService(room.service_id || room.lighting_service_id || room.lighting_service);
                  const cmdOn = checkBit(indicator_command_mask ?? null, room.led_bit);
                  const confOn = checkBit(indicator_confirmed_mask ?? null, room.led_bit);
                  return (
                    <div key={room.id} className={oom-card } style={{ border: '1px solid #e2e8f0', borderRadius: '0.75rem', padding: '1.25rem', background: '#fff' }}>
                      <div className="room-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                        <h4 style={{ margin: 0, fontSize: '1.125rem' }}>{room.name}</h4>
                        <span style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', background: '#f1f5f9', borderRadius: '1rem', color: '#64748b' }}>{room.id}</span>
                      </div>
                      
                      <div className="room-stats" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        <div className="stat-row" style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#64748b', fontSize: '0.875rem' }}>Service Level:</span>
                          <span style={{ fontWeight: 600 }}>{svc?.tier ?? 'UNKNOWN'}</span>
                        </div>
                        <div className="stat-row" style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#64748b', fontSize: '0.875rem' }}>Power Status:</span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: svc?.modeled_served ? '#22c55e' : '#ef4444' }}></span>
                            {svc?.modeled_served ? 'Served' : 'Shed'}
                          </span>
                        </div>
                        <div className="stat-row" style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#64748b', fontSize: '0.875rem' }}>LED Indicator:</span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: confOn ? '#3b82f6' : (cmdOn ? '#94a3b8' : '#e2e8f0') }}></span>
                            {confOn ? 'Confirmed ON' : (cmdOn ? 'Cmd ON' : 'OFF')}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}'''

dashboard = re.sub(
    r'<div className="classrooms-grid">[\s\S]*?</div>\s*</div>\s*</section>\s*\}',
    replacement,
    dashboard
)

dashboard = re.sub(
    r'\{activeTab === "hospital" && <section className="zone-section">[\s\S]*?</div>\s*</section>\s*\}',
    '',
    dashboard
)

# Update control buttons that used zones?.classroom
dashboard = re.sub(
    r'zones\?\.classroom\.active_classroom_id',
    'zones?.classroom?.active_classroom_id',
    dashboard
)
dashboard = re.sub(
    r'zones\.classroom\.active_classroom_id',
    'zones?.classroom?.active_classroom_id',
    dashboard
)

with open('frontend/src/pages/DemoDashboard.tsx', 'w', encoding='utf-8') as f:
    f.write(dashboard)
