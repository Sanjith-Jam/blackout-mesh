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
      {/* HOW IT DECIDES */}
      <section id="problem" className="content-section alternate">
        <div className="container">
          <h2 className="section-heading">How it decides</h2>
          <ol className="landing-steps">
            <li><span className="type-eyebrow">01 · Sense</span><h3>Read the grid and the rooms</h3><p>Feeder voltages, transformer readings, card taps and room sensors arrive as timestamped observations. Missing data stays unknown, never zero.</p></li>
            <li><span className="type-eyebrow">02 · Decide</span><h3>Protect first, then rank</h3><p>Every one of the 64 possible plans is checked. Critical circuits and classroom essentials come first; occupancy evidence only reorders optional loads.</p></li>
            <li><span className="type-eyebrow">03 · Explain</span><h3>Say why, or say “I don’t know”</h3><p>Each cut gets a reason and a counterfactual. Diagnosis ranks likely causes and abstains when sensors disagree or freeze.</p></li>
          </ol>
        </div>
      </section>

      {/* WHERE TO LOOK */}
      <section id="hospital" className="content-section">
        <div className="container">
          <h2 className="section-heading">Where to look</h2>
          <div className="features-grid landing-routes">
            <Link to="/demo" className="feature-panel"><div className="feature-icon"><Zap size={28} /></div><h3>City demo</h3><p>One event, the whole grid: request rooms, cause a shortage, trip a feeder and follow staged recovery.</p></Link>
            <Link to="/hospital" className="feature-panel"><div className="feature-icon"><HeartPulse size={28} /></div><h3>Hospital · feeder A</h3><p>Equipment behind three transformers. Inject overload, cooling failure or a stuck sensor and read the ranked causes.</p></Link>
            <Link to="/classrooms" className="feature-panel"><div className="feature-icon"><BookOpen size={28} /></div><h3>Classrooms · feeder B</h3><p>Scan a room card, lower supply and watch occupancy evidence decide which optional equipment stays on.</p></Link>
            <Link to="/console" className="feature-panel"><div className="feature-icon"><Activity size={28} /></div><h3>Engineering console</h3><p>Recorded history, playback and the raw controls behind every view.</p></Link>
          </div>
        </div>
      </section>

      {/* LIMITATIONS */}
      <section className="content-section limitations-section">
        <div className="container">
          <div className="limitations-box">
            <ShieldAlert className="warning-icon" size={32} />
            <div>
              <h3>What is real and what is simulated</h3>
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
