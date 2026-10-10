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
      <div className="hidden">
        <div className="hero-content">
          <h1 className="hero-title">
            Intelligent, Fault-Aware and Resilient<br />Power Management Network.
          </h1>
          <p className="hero-subtitle">
            An intelligent power-management demonstration that combines fault diagnosis, priority-aware allocation, explainable decisions, and RFID-based classroom indicators.
          </p>
          <div className="workflow-steps">
            <span>DETECT</span> <span className="arrow">→</span>
            <span>DIAGNOSE</span> <span className="arrow">→</span>
            <span>PRIORITIZE</span> <span className="arrow">→</span>
            <span>OPTIMIZE</span> <span className="arrow">→</span>
            <span>ACT</span> <span className="arrow">→</span>
            <span>EXPLAIN</span> <span className="arrow">→</span>
            <span>RECOVER</span>
          </div>
          <div className="hero-cta">
            <Link to="/demo" className="btn-primary btn-large">Launch Interactive Demo</Link>
            <a href="#architecture" className="btn-secondary btn-large">Explore Architecture</a>
          </div>
        </div>
        <div className="hero-visual">
          <div className="network-diagram">
            <div className="node source">
              <Zap size={24} />
              <span>Simulated Source</span>
            </div>
            <div className="lines">
              <div className="line left"></div>
              <div className="line right"></div>
            </div>
            <div className="feeders">
              <div className="node feeder">
                <span>Feeder A</span>
                <small>6000 W</small>
              </div>
              <div className="node feeder">
                <span>Feeder B</span>
                <small>8000 W</small>
              </div>
            </div>
          </div>
          </div>
        </div>
      {/* WHY PRIORITYGRID */}
      <section id="problem" className="content-section alternate">
        <div className="container">
          <h2 className="section-heading">Why PriorityGrid?</h2>
          <p className="section-text large">
            When available capacity becomes limited, not every modeled service can necessarily run. PriorityGrid evaluates simulated conditions, protects essential services wherever constraints permit, and explains the decisions.
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
                PriorityGrid is a locally hosted prototype. Electrical capacity, demand, fault conditions, load availability, and load shedding are <strong>simulated</strong>. RFID scans, ESP32 communication, and LED outputs are physical interactions when connected and verified. 
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
          <BenchmarkCard 
            title="Algorithm Decision Speed (ms)" 
            stats={[
              { label: "Rule-Based", value: 45 },
              { label: "Logistic Regression", value: 12 },
              { label: "PriorityGrid Engine", value: 95 }
            ]} 
          />
        </div>
      </section>



      {/* FOOTER */}
      <footer className="landing-footer relative z-10 p-8 border-t border-border bg-muted/50 backdrop-blur-md">
        <div className="container mx-auto flex flex-col md:flex-row justify-between items-center text-muted-foreground gap-4">
          <div className="footer-brand flex items-center gap-2 font-bold">
            <Activity size={20} /> PriorityGrid
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
