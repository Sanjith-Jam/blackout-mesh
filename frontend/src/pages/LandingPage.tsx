import { Link } from 'react-router-dom';
import { ShieldAlert, Zap, Activity, HeartPulse, BookOpen } from 'lucide-react';
import { HeroSection } from '@/components/ui/hero-section';
import { BenchmarkCard } from '@/components/ui/benchmark-card';
import { CircuitBoard } from '@/components/ui/circuit-board';
import './LandingPage.css';

export default function LandingPage() {
  return (
    <div className="landing-container relative min-h-screen">
      <CircuitBoard className="opacity-10" />
      
      {/* HERO SECTION */}
      <HeroSection />
      {/* WHY BLACKOUT MESH */}
      <section id="problem" className="content-section alternate">
        <div className="container">
          <h2 className="section-heading">Why Blackout Mesh?</h2>
          <p className="section-text large">
            When available capacity becomes limited, not every modeled service can necessarily run. Blackout Mesh evaluates simulated conditions, protects essential services wherever constraints permit, and explains the decisions.
          </p>
        </div>
      </section>

      {/* TWO DEMONSTRATION ENVIRONMENTS */}
      <section id="hospital" className="content-section">
        <div className="container">
          <h2 className="section-heading">Two Demonstration Environments</h2>
          <div className="features-grid">
            
            {/* Hospital Panel */}
            <div className="feature-panel">
              <div className="feature-icon"><HeartPulse size={32} /></div>
              <h3>Hospital Demonstration</h3>
              <ul className="feature-list">
                <li>Three hospital rooms with required room lighting</li>
                <li>Emergency lighting & Water pump operations</li>
                <li>Essential services strictly prioritized</li>
                <li><strong>Note:</strong> The three room lights share the L0 modeled service group.</li>
              </ul>
            </div>

            {/* Classroom Panel */}
            <div id="classrooms" className="feature-panel">
              <div className="feature-icon"><BookOpen size={32} /></div>
              <h3>Classroom Demonstration</h3>
              <ul className="feature-list">
                <li>Three independent classrooms</li>
                <li>One registered RFID card per classroom</li>
                <li>Simulated load events via interactive dashboard</li>
                <li>Only the selected, active, modeled-served classroom may have its indicator commanded ON.</li>
              </ul>
            </div>

          </div>
        </div>
      </section>



      {/* LIMITATIONS */}
      <section className="content-section limitations-section">
        <div className="container">
          <div className="limitations-box">
            <ShieldAlert className="warning-icon" size={32} />
            <div>
              <h3>Prototype Limitations</h3>
              <p>
                Blackout Mesh is a locally hosted prototype. Electrical capacity, demand, fault conditions, load availability, and load shedding are <strong>simulated</strong>. RFID scans, ESP32 communication, and LED outputs are physical interactions when connected and verified.
                <br /><br />
                The LEDs indicate modeled states, not actual power delivery. This does not represent certified hospital infrastructure or verified electrical-code compliance.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* PERFORMANCE BENCHMARK */}
      <section className="content-section alternate relative z-10 p-12">
        <div className="container mx-auto max-w-4xl">
          <BenchmarkCard />
        </div>
      </section>



      {/* FOOTER */}
      <footer className="landing-footer relative z-10 p-8 border-t border-border bg-muted/50 backdrop-blur-md">
        <div className="container mx-auto flex flex-col md:flex-row justify-between items-center text-muted-foreground gap-4">
          <div className="footer-brand flex items-center gap-2 font-bold">
            <Activity size={20} /> Blackout Mesh
          </div>
          <div className="footer-disclaimer text-sm text-center">
            Offline decision console demonstration. Not for production life-safety use.
          </div>
          <div className="footer-links">
            <Link to="/demo" className="hover:text-primary">Interactive Demo</Link>
          </div>
        </div>
      </footer>

    </div>
  );
}
