import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Activity, RefreshCw, Server, Wifi, AlertTriangle } from 'lucide-react';
import { fetchHealth, fetchSnapshot, processRfidScan, changeCapacity, changeClassroomLoad, changeFeeder } from '../api';
import { Snapshot } from '../types';
import './DemoDashboard.css';

export default function DemoDashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [healthOk, setHealthOk] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<{msg: string, isError: boolean} | null>(null);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    
    try {
      const abortController = new AbortController();
      const timeoutId = setTimeout(() => abortController.abort(), 10000);
      
      const [health, snap] = await Promise.all([
        fetchHealth(abortController.signal).catch(() => ({ status: 'error', application: '' })),
        fetchSnapshot(abortController.signal)
      ]);
      
      clearTimeout(timeoutId);
      
      setHealthOk(health.status === 'ok');
      setSnapshot(snap);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
      setHealthOk(false);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAction = async (actionFn: () => Promise<any>, successMsg: string) => {
    if (actionPending) return;
    setActionPending(true);
    setActionFeedback(null);
    try {
      const res = await actionFn();
      if (res.accepted) {
        setActionFeedback({ msg: successMsg, isError: false });
      } else {
        setActionFeedback({ msg: `Action rejected: ${res.event_type || 'Constraints violated'}`, isError: true });
      }
      await loadData(true);
    } catch (err: any) {
      setActionFeedback({ msg: `Failed: ${err.message}`, isError: true });
    } finally {
      setActionPending(false);
      // clear feedback after 3s
      setTimeout(() => setActionFeedback(null), 3000);
    }
  };

  const doRfidScan = (uid: string) => handleAction(() => processRfidScan(uid), `RFID Scan processed for ${uid}`);
  const doClassroomLoad = (cid: string, active: boolean) => handleAction(() => changeClassroomLoad(cid, active), `Classroom ${cid} load set to ${active}`);
  const doCapacity = (watts: number) => handleAction(() => changeCapacity(watts), `Capacity set to ${watts}W`);
  const doFeeder = (feeder: string, available: boolean) => handleAction(() => changeFeeder(feeder, available), `Feeder ${feeder} available: ${available}`);

  if (loading && !snapshot) {
    return (
      <div className="dashboard-container loading">
        <Activity className="spin" size={48} />
        <h2>Loading Control Room...</h2>
      </div>
    );
  }

  if (error && !snapshot) {
    return (
      <div className="dashboard-container error-state">
        <AlertTriangle size={48} color="#ef4444" />
        <h2>Connection Lost</h2>
        <p>{error}</p>
        <button className="btn-primary" onClick={() => loadData()}>Retry Connection</button>
      </div>
    );
  }

  if (!snapshot) return null;

  const { services, zones, source, feeder_limits_w, control_revision, indicator_command_mask, indicator_confirmed_mask } = snapshot;
  
  const servedWatts = services.filter(s => s.modeled_served).reduce((sum, s) => sum + s.watts, 0);
  const servedCount = services.filter(s => s.modeled_served).length;
  const feederAWatts = services.filter(s => s.modeled_served && s.feeder === 'A').reduce((sum, s) => sum + s.watts, 0);
  const feederBWatts = services.filter(s => s.modeled_served && s.feeder === 'B').reduce((sum, s) => sum + s.watts, 0);

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
            <span className="brand-badge">Interactive Demo</span>
          </div>
        </div>
        
        <div className="dash-status-indicators">
          <div className={`status-pill ${healthOk ? 'ok' : 'error'}`}>
            <Server size={14} /> Backend {healthOk ? 'Connected' : 'Stale'}
          </div>
          <div className="status-pill warn">
            <Wifi size={14} /> HW: {snapshot.hardware_link.replace('_', ' ')}
          </div>
        </div>

        <div className="dash-actions">
          <Link to="/" className="btn-secondary">Back to Home</Link>
          <button className="btn-primary icon-btn" onClick={() => loadData(true)} disabled={refreshing}>
            <RefreshCw size={16} className={refreshing ? 'spin' : ''} />
          </button>
        </div>
      </header>

      {error && (
        <div className="dash-alert error">
          <AlertTriangle size={16} /> Backend disconnected. Displaying stale snapshot.
        </div>
      )}

      {/* OVERVIEW STRIP */}
      <section className="overview-strip">
        <div className="metric-box">
          <div className="metric-label">Simulated Capacity</div>
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

      {/* FEEDER BARS */}
      <section className="feeders-strip">
        <div className="feeder-bar-container">
          <div className="feeder-header">
            <span>Feeder A (Hospital)</span>
            <span>{feederAWatts} / {feeder_limits_w.A} W</span>
          </div>
          <div className="progress-bg">
            <div className={`progress-fill ${feederAWatts > feeder_limits_w.A ? 'over' : ''}`} style={{width: `${Math.min(100, (feederAWatts / feeder_limits_w.A) * 100)}%`}}></div>
          </div>
        </div>
        <div className="feeder-bar-container">
          <div className="feeder-header">
            <span>Feeder B (Classrooms)</span>
            <span>{feederBWatts} / {feeder_limits_w.B} W</span>
          </div>
          <div className="progress-bg">
            <div className={`progress-fill ${feederBWatts > feeder_limits_w.B ? 'over' : ''}`} style={{width: `${Math.min(100, (feederBWatts / feeder_limits_w.B) * 100)}%`}}></div>
          </div>
        </div>
      </section>

      <div className="zones-layout">
        <div className="main-zones">
          
          {/* HOSPITAL ZONE */}
          <section className="zone-section">
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
          </section>

          {/* CLASSROOM ZONE */}
          <section className="zone-section">
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
          </section>
          
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
              <button className="btn-outline" disabled={actionPending} onClick={() => doRfidScan('CARD_1_UID')}>Scan Classroom 1</button>
              <button className="btn-outline" disabled={actionPending} onClick={() => doRfidScan('CARD_2_UID')}>Scan Classroom 2</button>
              <button className="btn-outline" disabled={actionPending} onClick={() => doRfidScan('CARD_3_UID')}>Scan Classroom 3</button>
              <button className="btn-outline err" disabled={actionPending} onClick={() => doRfidScan('UNKNOWN_CARD_UID')}>Scan Unknown Card</button>
            </div>

            <div className="control-group">
              <h3>Classroom Load Control</h3>
              <p className="control-desc">Simulate electrical demand for the selected classroom.</p>
              {zones?.classroom.active_classroom_id ? (
                <div className="flex-buttons">
                  <button className="btn-outline" disabled={actionPending} onClick={() => doClassroomLoad(zones.classroom.active_classroom_id!, true)}>Activate Load</button>
                  <button className="btn-outline" disabled={actionPending} onClick={() => doClassroomLoad(zones.classroom.active_classroom_id!, false)}>Deactivate Load</button>
                </div>
              ) : (
                <div className="text-err text-small">Select a classroom first.</div>
              )}
            </div>

            <div className="control-group">
              <h3>Power Scenarios</h3>
              <p className="control-desc">Test fault detection and constrained optimization.</p>
              <button className="btn-outline" disabled={actionPending} onClick={() => {
                doCapacity(14000);
                doFeeder('A', true);
                doFeeder('B', true);
              }}>Normal Conditions</button>
              
              <button className="btn-outline warn" disabled={actionPending} onClick={() => doCapacity(6000)}>Shortage (6000W)</button>
              <button className="btn-outline err" disabled={actionPending} onClick={() => doFeeder('A', false)}>Feeder A Loss</button>
              <button className="btn-outline err" disabled={actionPending} onClick={() => doFeeder('B', false)}>Feeder B Loss</button>
            </div>

          </div>
        </aside>
      </div>
    </div>
  );
}
