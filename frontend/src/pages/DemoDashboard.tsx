import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Server, Wifi, AlertTriangle } from 'lucide-react';
import { processRfidScan, changeCapacity, changeClassroomLoad, changeFeeder, getWebSocketUrl } from '../api';
import { Snapshot } from '../types';
import TopologyGraph from '../components/TopologyGraph';
import SourceCapacityDemandChart from '../components/SourceCapacityDemandChart';
import AllocationHistoryChart from '../components/AllocationHistoryChart';
import IncidentTimeline from '../components/IncidentTimeline';
import './DemoDashboard.css';
import { useServerHistory } from '../history';
import HistoryControls from '../components/HistoryControls';

export default function DemoDashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [liveSnapshot, setLiveSnapshot] = useState<Snapshot | null>(null);
  const [healthOk, setHealthOk] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<{msg: string, isError: boolean} | null>(null);

  const historyData = useServerHistory(liveSnapshot?.events || []);
  const snapshot = historyData.selection.mode === 'HISTORY' ? historyData.snapshot : liveSnapshot;
  const history = historyData.telemetry;

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (historyData.selection.mode !== 'LIVE') return;
    let stopped = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const connectWs = () => {
      if (stopped) return;
      const ws = new WebSocket(getWebSocketUrl());
      wsRef.current = ws;
      ws.onmessage = event => {
        if (stopped) return;
        try {
          const data: Snapshot = JSON.parse(event.data);
          setLiveSnapshot(data);
          setHealthOk(true);
          setError(null);
        } catch { setError('Invalid live snapshot received.'); }
      };
      ws.onclose = () => {
        if (stopped) return;
        setHealthOk(false);
        setError('WebSocket disconnected. Backfilling server history on reconnect…');
        retryTimer = setTimeout(connectWs, 3000);
      };
    };
    connectWs();
    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [historyData.selection.mode]);

  const handleAction = async (actionFn: () => Promise<any>, successMsg: string) => {
    if (actionPending || historyData.selection.mode === 'HISTORY') return;
    setActionPending(true);
    setActionFeedback(null);
    try {
      const res = await actionFn();
      if (res.accepted) {
        setActionFeedback({ msg: successMsg, isError: false });
      } else {
        setActionFeedback({ msg: `Action rejected: ${res.event_type || 'Constraints violated'}`, isError: true });
      }
    } catch (err: any) {
      setActionFeedback({ msg: `Failed: ${err.message}`, isError: true });
    } finally {
      setActionPending(false);
      setTimeout(() => setActionFeedback(null), 3000);
    }
  };

  const doRfidScan = (uid: string) => handleAction(() => processRfidScan(uid), `RFID Scan processed for ${uid}`);
  const doClassroomLoad = (cid: string, active: boolean) => handleAction(() => changeClassroomLoad(cid, active), `Classroom ${cid} load set to ${active}`);
  const doCapacity = (watts: number) => handleAction(() => changeCapacity(watts), `Capacity set to ${watts}W`);
  const doFeeder = (feeder: string, available: boolean) => handleAction(() => changeFeeder(feeder, available), `Feeder ${feeder} available: ${available}`);

  if (!snapshot) {
    return (
      <div className="dashboard-container loading">
        <HistoryControls history={historyData} />
<Activity className="spin" size={48} />
        <h2>{historyData.selection.mode === 'HISTORY' ? 'Select a recorded run and range' : 'Connecting to Live Feed...'}</h2>
        {error && <p className="text-err">{error}</p>}
      </div>
    );
  }

  const { services, zones, source, control_revision, indicator_command_mask, indicator_confirmed_mask } = snapshot;
  
  const servedWatts = services.filter(s => s.modeled_served).reduce((sum, s) => sum + s.watts, 0);
  const servedCount = services.filter(s => s.modeled_served).length;

  const getService = (id: string) => services.find(s => s.id === id);
  const l0 = getService('L0');
  const l1 = getService('L1');
  const l2 = getService('L2');

  const checkBit = (mask: number | null, bit: number) => {
    if (mask === null) return null;
    return Boolean((mask >> bit) & 1);
  };

  return (
    <div className="dashboard-container">
      {/* HEADER */}
      <header className="dash-header">
        <div className="dash-brand">
          <Activity className="brand-icon" />
          <div>
            <span className="brand-name">PriorityGrid</span>
            <span className="brand-badge">{historyData.selection.mode} Console{snapshot?.site ? ` · run ${snapshot.site.run_id} · rev ${snapshot.site.revision}` : ''}</span>
          </div>
        </div>
        
        <div className="dash-status-indicators">
          <div className={`status-pill ${healthOk ? 'ok' : 'error'}`}>
            <Server size={14} /> Backend {historyData.selection.mode === 'HISTORY' ? 'Recorded evidence' : healthOk ? 'Live' : 'Disconnected'}
          </div>
          <div className="status-pill warn">
            <Wifi size={14} /> {historyData.selection.mode === 'HISTORY' ? 'Recorded HW:' : 'HW:'} {snapshot.hardware_link.replace('_', ' ')}
          </div>
        </div>

        <div className="dash-actions">
          <Link to="/" className="btn-secondary">Back to Home</Link>
        </div>
      </header>

      {error && historyData.selection.mode === 'LIVE' && (
        <div className="dash-alert error">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      <HistoryControls history={historyData} />
      {/* OVERVIEW STRIP */}
      <section className="overview-strip">
        <div className="metric-box">
          <div className="metric-label">Live Capacity</div>
          <div className="metric-value">{source.capacity_w} <small>W</small></div>
        </div>
        <div className="metric-box">
          <div className="metric-label">Modeled Services</div>
          <div className="metric-value">{servedCount} <small>/ {services.length}</small></div>
        </div>
        <div className="metric-box">
          <div className="metric-label">Modeled Demand</div>
          <div className="metric-value">{servedWatts} <small>W</small></div>
        </div>
        <div className="metric-box">
          <div className="metric-label">Control Revision</div>
          <div className="metric-value">{control_revision}</div>
        </div>
      </section>

      {/* VISUALIZATIONS ROW */}
      <section className="visualizations-row" style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <div className="vis-panel" style={{ flex: '1 1 300px', background: '#fff', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
          <h3 style={{ margin: '0 0 10px 0', fontSize: '1.1rem' }}>Source vs Demand</h3>
          <SourceCapacityDemandChart data={history} />
        </div>
        <div className="vis-panel" style={{ flex: '1 1 300px', background: '#fff', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
          <h3 style={{ margin: '0 0 10px 0', fontSize: '1.1rem' }}>Allocation History</h3>
          <AllocationHistoryChart data={history} />
        </div>
        <div className="vis-panel" style={{ flex: '1 1 300px' }}>
          <IncidentTimeline events={historyData.events} />
        </div>
      </section>

      {/* TOPOLOGY & ZONES ROW */}
      
      <div className="demo-tabs" style={{ display: 'flex', gap: '1rem', padding: '0 0', borderBottom: '1px solid #e2e8f0', background: 'transparent', marginBottom: '1.5rem' }}>
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')} style={{ padding: '0.75rem 1.5rem', border: 'none', background: 'none', borderBottom: activeTab === 'overview' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600, fontSize: '1rem' }}>Overview</button>
        <button className={`tab-btn ${activeTab === 'hospital' ? 'active' : ''}`} onClick={() => setActiveTab('hospital')} style={{ padding: '0.75rem 1.5rem', border: 'none', background: 'none', borderBottom: activeTab === 'hospital' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600, fontSize: '1rem' }}>Hospital Zone</button>
        <button className={`tab-btn ${activeTab === 'classrooms' ? 'active' : ''}`} onClick={() => setActiveTab('classrooms')} style={{ padding: '0.75rem 1.5rem', border: 'none', background: 'none', borderBottom: activeTab === 'classrooms' ? '2px solid #0f172a' : '2px solid transparent', cursor: 'pointer', fontWeight: 600, fontSize: '1rem' }}>Classroom Zone</button>
      </div>

      <div className="zones-layout">
        <div className="main-zones">
          
          {/* NETWORK TOPOLOGY */}
          {activeTab === "overview" && <section className="zone-section">
            <div className="zone-header">
              <h2>Network Topology</h2>
              <p>Real-time physical modeled connections.</p>
            </div>
            <TopologyGraph snapshot={snapshot} />
          </section>}

          {/* HOSPITAL ZONE */}
          {activeTab === "hospital" && <section className="zone-section">
            <div className="zone-header">
              <h2>Hospital Zone</h2>
              <p>Three rooms with shared essential lighting and priority-aware support services.</p>
            </div>
            
            <div className="hospital-rooms-grid">
              {zones?.hospital.rooms.map(room => {
                const cmdOn = checkBit(indicator_command_mask, room.led_bit);
                const confOn = checkBit(indicator_confirmed_mask, room.led_bit);
                return (
                  <div key={room.id} className="room-card">
                    <h3>{room.name}</h3>
                    <div className="room-tag">Follows L0</div>
                    <div className="led-states">
                      <div className="led-row">
                        <span>Cmd:</span>
                        <span className={`led-badge ${cmdOn ? 'on' : 'off'}`}>{cmdOn ? 'ON' : 'OFF'}</span>
                      </div>
                      <div className="led-row">
                        <span>HW:</span>
                        <span className="led-badge unknown">{confOn === null ? 'Unknown' : (confOn ? 'ON' : 'OFF')}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="hospital-services">
              {[l0, l1, l2].map(svc => svc && (
                <div key={svc.id} className={`service-row ${svc.modeled_served ? 'served' : 'shed'}`}>
                  <div className="svc-info">
                    <strong>{svc.id} - {svc.name}</strong>
                    <span className="svc-meta">{svc.tier} | {svc.watts}W | Feeder {svc.feeder}</span>
                  </div>
                  <div className="svc-status">
                    {svc.modeled_served ? <span className="text-ok">Served</span> : <span className="text-err">Shed</span>}
                  </div>
                  <div className="svc-reason">{svc.model_reason}</div>
                </div>
              ))}
            </div>
          </section>}

          {/* CLASSROOM ZONE */}
          {activeTab === "classrooms" && <section className="zone-section">
            <div className="zone-header">
              <h2>RFID Classroom Zone</h2>
              <p>Select a classroom, activate a simulated load event, and observe the backend's allocation decision and indicator state.</p>
            </div>
            
            <div className="classrooms-grid">
              {zones?.classroom.classrooms.map(cr => {
                const isSelected = zones.classroom.active_classroom_id === cr.id;
                const svc = getService(cr.service_id);
                const cmdOn = checkBit(indicator_command_mask, cr.led_bit);
                const confOn = checkBit(indicator_confirmed_mask, cr.led_bit);

                return (
                  <div key={cr.id} className={`cr-card ${isSelected ? 'selected' : ''}`}>
                    <div className="cr-header">
                      <h3>{cr.name}</h3>
                      {isSelected && <span className="cr-active-badge">Active Selection</span>}
                    </div>
                    
                    <div className="cr-props">
                      <span>Service {cr.service_id}</span>
                      <span>Priority {svc?.tier}</span>
                      <span>{svc?.watts} W</span>
                    </div>

                    <div className="cr-states">
                      <div className="state-line">
                        <span className="label">Simulated Load:</span>
                        <span className={`value ${cr.load_event_active ? 'text-ok' : 'text-off'}`}>
                          {cr.load_event_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      <div className="state-line">
                        <span className="label">Modeled Service:</span>
                        <span className={`value ${svc?.modeled_served ? 'text-ok' : 'text-err'}`}>
                          {svc?.modeled_served ? 'Served' : 'Shed'}
                        </span>
                      </div>
                      <div className="state-line">
                        <span className="label">Indicator Cmd:</span>
                        <span className={`led-badge ${cmdOn ? 'on' : 'off'}`}>{cmdOn ? 'ON' : 'OFF'}</span>
                      </div>
                      <div className="state-line">
                        <span className="label">Hardware Conf:</span>
                        <span className="led-badge unknown">{confOn === null ? 'Unknown' : (confOn ? 'ON' : 'OFF')}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>}
          
        </div>

        {/* DEMO CONTROLS SIDEBAR */}
        <aside className="demo-controls-sidebar">
          <div className="controls-panel">
            <h2>Demo Controls</h2>
            
            {actionFeedback && (
              <div className={`feedback-toast ${actionFeedback.isError ? 'error' : 'success'}`}>
                {actionFeedback.msg}
              </div>
            )}

            <div className="control-group">
              <h3>RFID Selection</h3>
              <p className="control-desc">Simulate a physical card scan.</p>
              <button className="btn-outline" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doRfidScan('CARD_1_UID')}>Scan Classroom 1</button>
              <button className="btn-outline" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doRfidScan('CARD_2_UID')}>Scan Classroom 2</button>
              <button className="btn-outline" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doRfidScan('CARD_3_UID')}>Scan Classroom 3</button>
              <button className="btn-outline err" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doRfidScan('UNKNOWN_CARD_UID')}>Scan Unknown Card</button>
            </div>

            <div className="control-group">
              <h3>Classroom Load Control</h3>
              <p className="control-desc">Simulate electrical demand for the selected classroom.</p>
              {zones?.classroom.active_classroom_id ? (
                <div className="flex-buttons">
                  <button className="btn-outline" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doClassroomLoad(zones.classroom.active_classroom_id!, true)}>Activate Load</button>
                  <button className="btn-outline" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doClassroomLoad(zones.classroom.active_classroom_id!, false)}>Deactivate Load</button>
                </div>
              ) : (
                <div className="text-err text-small">Select a classroom first.</div>
              )}
            </div>

            <div className="control-group">
              <h3>Power Scenarios</h3>
              <p className="control-desc">Test fault detection and constrained optimization.</p>
              <button className="btn-outline" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => {
                doCapacity(14000);
                doFeeder('A', true);
                doFeeder('B', true);
              }}>Normal Conditions</button>
              
              <button className="btn-outline warn" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doCapacity(6000)}>Shortage (6000W)</button>
              <button className="btn-outline err" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doFeeder('A', false)}>Feeder A Loss</button>
              <button className="btn-outline err" disabled={actionPending || historyData.selection.mode === 'HISTORY'} onClick={() => doFeeder('B', false)}>Feeder B Loss</button>
            </div>

          </div>
        </aside>
      </div>
    </div>
  );
}
