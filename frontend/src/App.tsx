import { useState, useEffect, useCallback } from 'react';
import { fetchHealth, fetchSnapshot } from './api';
import { Snapshot, Service } from './types';
import './App.css';

function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [healthOk, setHealthOk] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    
    try {
      const abortController = new AbortController();
      const timeoutId = setTimeout(() => abortController.abort(), 10000);
      
      const [health, snap] = await Promise.all([
        fetchHealth(abortController.signal).catch(() => ({ status: 'error' })),
        fetchSnapshot(abortController.signal)
      ]);
      
      clearTimeout(timeoutId);
      
      setHealthOk(health.status === 'ok');
      setSnapshot(snap);
      setLastRefreshTime(new Date());
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

  if (loading && !snapshot) {
    return <div className="dashboard-container"><div className="loading-container">Loading system state...</div></div>;
  }

  if (error && !snapshot) {
    return (
      <div className="dashboard-container">
        <div className="error-panel">
          <h2 className="error-title">Backend Connection Failed</h2>
          <p>{error}</p>
          <p>The frontend is unable to reach the FastAPI backend at the configured URL.</p>
          <button className="refresh-btn" style={{marginTop: '1rem'}} onClick={() => loadData()}>Retry Connection</button>
          <ul className="error-instructions">
            <li>Ensure the FastAPI backend is running.</li>
            <li>Confirm that http://127.0.0.1:8000/api/v1/health responds successfully.</li>
            <li>Check the configured API base URL.</li>
            <li>Inspect the browser console and Network panel for connection errors.</li>
          </ul>
        </div>
      </div>
    );
  }

  if (!snapshot) return null;

  const modeledServedCount = snapshot.services.filter(s => s.modeled_served).length;
  const requestedCount = snapshot.services.filter(s => s.requested).length;
  const totalServices = snapshot.services.length;

  const servedWattsTotal = snapshot.services
    .filter(s => s.modeled_served)
    .reduce((sum, s) => sum + s.watts, 0);
    
  const feederAWatts = snapshot.services
    .filter(s => s.modeled_served && s.feeder === 'A')
    .reduce((sum, s) => sum + s.watts, 0);

  const feederBWatts = snapshot.services
    .filter(s => s.modeled_served && s.feeder === 'B')
    .reduce((sum, s) => sum + s.watts, 0);

  return (
    <div className="dashboard-container">
      {/* 1. Header */}
      <header className="app-header">
        <div className="brand">
          <h1>PriorityGrid</h1>
          <span className="brand-descriptor">Intelligent Power Management Network</span>
        </div>
        <div className="header-controls">
          <div className="status-badge" title="Backend API Health">
            <span className={`status-dot ${healthOk ? 'ok' : 'error'}`}></span>
            {healthOk ? 'API Connected' : 'API Offline'}
          </div>
          <button 
            className="refresh-btn" 
            onClick={() => loadData(true)} 
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </header>
      
      {error && (
        <div className="error-panel" style={{marginBottom: 0}}>
          <h2 className="error-title">Refresh Failed</h2>
          <p>{error}. Displaying stale snapshot.</p>
        </div>
      )}

      {/* 2. System Overview */}
      <section className="dashboard-section">
        <h2 className="section-title">System Overview</h2>
        <div className="overview-grid">
          <div className="metric-card">
            <div className="metric-label">Source Capacity</div>
            <div className="metric-value">{snapshot.source.capacity_w.toLocaleString()} W</div>
            <div className="metric-sub">{(snapshot.source.capacity_w / 1000).toFixed(1)} kW</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Modeled Served</div>
            <div className="metric-value">{modeledServedCount} / {totalServices}</div>
            <div className="metric-sub">{requestedCount} services requested</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Modeled Load</div>
            <div className="metric-value">{servedWattsTotal.toLocaleString()} W</div>
            <div className="metric-sub">Derived from served units</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Control Revision</div>
            <div className="metric-value">Rev {snapshot.control_revision}</div>
            <div className="metric-sub">Hardware Link: {snapshot.hardware_link.replace(/_/g, ' ')}</div>
          </div>
        </div>
      </section>

      {/* 3. Capacity Section */}
      <section className="dashboard-section">
        <h2 className="section-title">Capacity & Utilization</h2>
        <div className="capacity-grid">
          <div className="capacity-item">
            <div className="capacity-header">
              <span className="capacity-title">Simulated Source</span>
              <span className="capacity-value">{servedWattsTotal.toLocaleString()} / {snapshot.source.capacity_w.toLocaleString()} W</span>
            </div>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${Math.min(100, (servedWattsTotal / snapshot.source.capacity_w) * 100 || 0)}%` }}
              ></div>
            </div>
          </div>
          
          <div className="capacity-item">
            <div className="capacity-header">
              <span className="capacity-title">Feeder A Limit</span>
              <span className="capacity-value">{feederAWatts.toLocaleString()} / {snapshot.feeder_limits_w.A.toLocaleString()} W</span>
            </div>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${Math.min(100, (feederAWatts / snapshot.feeder_limits_w.A) * 100 || 0)}%` }}
              ></div>
            </div>
          </div>
          
          <div className="capacity-item">
            <div className="capacity-header">
              <span className="capacity-title">Feeder B Limit</span>
              <span className="capacity-value">{feederBWatts.toLocaleString()} / {snapshot.feeder_limits_w.B.toLocaleString()} W</span>
            </div>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${Math.min(100, (feederBWatts / snapshot.feeder_limits_w.B) * 100 || 0)}%` }}
              ></div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Services Grid */}
      <section className="dashboard-section">
        <h2 className="section-title">Service Allocations</h2>
        <div className="services-grid">
          {snapshot.services.map((service: Service) => (
            <div className="service-card" key={service.id}>
              <div className="service-header">
                <div className="service-identity">
                  <span className="service-id">{service.id}</span>
                  <span className="service-name">{service.name}</span>
                </div>
                <div className="service-power">
                  {service.watts.toLocaleString()} W
                </div>
              </div>
              
              <div className="service-badges">
                <span className="badge">{service.tier}</span>
                <span className="badge">Feeder {service.feeder}</span>
              </div>
              
              <div className="service-states">
                <div className="state-row">
                  <span className="state-label">Requested</span>
                  <span className="state-value">
                    <span className={`status-dot ${service.requested ? 'ok' : 'offline'}`}></span>
                    {service.requested ? 'Yes' : 'No'}
                  </span>
                </div>
                
                <div className="state-row">
                  <span className="state-label">Modeled</span>
                  <span className="state-value">
                    <span className={`status-dot ${service.modeled_served ? 'ok' : 'offline'}`}></span>
                    {service.modeled_served ? 'Served' : 'Not Served'}
                  </span>
                </div>
                
                <div className="state-row">
                  <span className="state-label">Hardware Status</span>
                  <span className="state-value">
                    <span className={`status-dot ${
                      service.indicator_confirmed === true ? 'ok' : 
                      service.indicator_confirmed === false ? 'offline' : 'unknown'
                    }`}></span>
                    {service.indicator_confirmed === true ? 'Confirmed' : 
                     service.indicator_confirmed === false ? 'Not Confirmed' : 'Unknown'}
                  </span>
                </div>
                
                {service.model_reason && (
                  <div className="reason-text">{service.model_reason}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 5. Hardware Status Panel */}
      <section className="dashboard-section">
        <h2 className="section-title">Hardware & Observability</h2>
        <div className="hardware-grid">
          <div className="metric-card">
            <div className="metric-label">Hardware Link</div>
            <div className="metric-value" style={{fontSize: '1.25rem'}}>{snapshot.hardware_link.replace(/_/g, ' ')}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Indicator Mask</div>
            <div className="metric-value" style={{fontSize: '1.25rem'}}>
              {snapshot.indicator_mask !== null ? snapshot.indicator_mask : 'Unknown'}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Modeled Mask</div>
            <div className="metric-value" style={{fontSize: '1.25rem'}}>{snapshot.modeled_mask}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Requested Mask</div>
            <div className="metric-value" style={{fontSize: '1.25rem'}}>{snapshot.requested_mask}</div>
          </div>
        </div>
      </section>

      {/* 6. Metadata Footer */}
      <footer className="metadata-footer">
        <div className="metadata-item">
          <span className="metadata-label">Control Revision</span>
          <span>{snapshot.control_revision}</span>
        </div>
        <div className="metadata-item">
          <span className="metadata-label">Snapshot Generation Time</span>
          <span>{new Date(snapshot.generated_at).toLocaleString()}</span>
        </div>
        <div className="metadata-item">
          <span className="metadata-label">Source Kind</span>
          <span>{snapshot.source.kind}</span>
        </div>
        <div className="metadata-item">
          <span className="metadata-label">Last Frontend Refresh</span>
          <span>{lastRefreshTime ? lastRefreshTime.toLocaleTimeString() : 'N/A'}</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
