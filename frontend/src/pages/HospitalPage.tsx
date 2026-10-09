import { Link } from 'react-router-dom';
import { HeartPulse, Activity } from 'lucide-react';
import './LandingPage.css'; // Reuse landing page styles

export default function HospitalPage() {
  return (
    <div className="landing-container">
      <header className="landing-header">
        <div className="landing-brand">
          <Activity className="brand-icon" />
          <span className="brand-name">PriorityGrid</span>
        </div>
        <nav className="landing-nav">
          <Link to="/">Overview</Link>
          <Link to="/hospital" className="active">Hospital</Link>
          <Link to="/classrooms">Classrooms</Link>
        </nav>
        <div className="landing-actions">
          <Link to="/demo" className="btn-primary">Launch Demo</Link>
        </div>
      </header>

      <section className="content-section">
        <div className="container">
          <div className="feature-icon" style={{ margin: '0 auto 1.5rem', display: 'flex', justifyContent: 'center' }}>
            <HeartPulse size={64} color="#0284c7" />
          </div>
          <h2 className="section-heading" style={{ textAlign: 'center' }}>Hospital Demonstration Zone</h2>
          <p className="section-text large" style={{ textAlign: 'center', maxWidth: '800px', margin: '0 auto 2rem' }}>
            The hospital zone models an environment where power continuity is critical for life-safety operations. 
            When capacity is constrained, PriorityGrid aggressively sheds lower-tier loads to preserve essential services here.
          </p>

          <div className="features-grid">
            <div className="feature-panel">
              <h3>Essential Lighting (L0)</h3>
              <p>Three interconnected hospital rooms sharing a single tier-1 service allocation. If L0 is shed, all three rooms lose indicator status.</p>
            </div>
            <div className="feature-panel">
              <h3>Emergency Lighting (L1)</h3>
              <p>Highest priority dedicated circuit. Always preserved unless physical feeder limits are exceeded.</p>
            </div>
            <div className="feature-panel">
              <h3>Water Pump (L2)</h3>
              <p>Tier-2 service providing essential infrastructure support, but expendable before life-safety tier-1 loads.</p>
            </div>
          </div>

          <div style={{ textAlign: 'center', marginTop: '3rem' }}>
            <Link to="/demo" className="btn-primary btn-large">View in Interactive Demo</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
