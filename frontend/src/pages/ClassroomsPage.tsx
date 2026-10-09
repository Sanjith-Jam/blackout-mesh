import { Link } from 'react-router-dom';
import { BookOpen, Activity } from 'lucide-react';
import './LandingPage.css'; // Reuse landing page styles

export default function ClassroomsPage() {
  return (
    <div className="landing-container">
      <header className="landing-header">
        <div className="landing-brand">
          <Activity className="brand-icon" />
          <span className="brand-name">PriorityGrid</span>
        </div>
        <nav className="landing-nav">
          <Link to="/">Overview</Link>
          <Link to="/hospital">Hospital</Link>
          <Link to="/classrooms" className="active">Classrooms</Link>
        </nav>
        <div className="landing-actions">
          <Link to="/demo" className="btn-primary">Launch Demo</Link>
        </div>
      </header>

      <section className="content-section">
        <div className="container">
          <div className="feature-icon" style={{ margin: '0 auto 1.5rem', display: 'flex', justifyContent: 'center' }}>
            <BookOpen size={64} color="#0284c7" />
          </div>
          <h2 className="section-heading" style={{ textAlign: 'center' }}>Classrooms Demonstration Zone</h2>
          <p className="section-text large" style={{ textAlign: 'center', maxWidth: '800px', margin: '0 auto 2rem' }}>
            The classroom zone explores physical integration using RFID authentication.
            Lower priority than the hospital, these services are among the first to be shed during capacity shortages.
          </p>

          <div className="features-grid">
            <div className="feature-panel">
              <h3>RFID Selection</h3>
              <p>Each of the three classrooms is mapped to a registered RFID card. Scanning a card sets the active classroom for the load event.</p>
            </div>
            <div className="feature-panel">
              <h3>Simulated Load</h3>
              <p>An indicator is only driven when a classroom is both selected and has an active simulated load event demanding power.</p>
            </div>
            <div className="feature-panel">
              <h3>Tiered Shedding</h3>
              <p>Classroom 1 and 2 (L3, L4) are Tier-2. Classroom 3 (L5) requires more power and is Tier-3, making it the very first load to be shed system-wide.</p>
            </div>
          </div>

          <div style={{ textAlign: 'center', marginTop: '3rem' }}>
            <Link to="/demo" className="btn-primary btn-large">Try RFID in Demo</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
