import { Link } from 'react-router-dom';
import { Activity, ArrowRight, ArrowUpRight, BookOpen, Cpu, ShieldCheck, Zap } from 'lucide-react';
import './LandingPage.css';

export default function LandingPage() {
  return <main className="landing">
    <header className="landing-header">
      <Link to="/" className="landing-brand"><span><Activity size={19} /></span><b>BLACKOUT <i>MESH</i></b></Link>
      <nav aria-label="Main navigation"><a href="#approach">Approach</a><a href="#scope">Scope</a></nav>
      <Link to="/demo" className="landing-launch">Open command center <ArrowUpRight size={15} /></Link>
    </header>
    <section className="landing-hero">
      <div className="landing-copy"><div className="landing-kicker"><span /> SOFTWARE DECISION SIMULATION</div><h1>Power decisions,<br /><em>made legible.</em></h1><p>Blackout Mesh explores how room activity evidence can inform a constrained campus power allocation, while fixed critical priorities stay ahead when source and feeder limits permit.</p><div className="landing-ctas"><Link to="/demo" className="landing-primary">Explore the simulation <ArrowRight size={16} /></Link><a className="landing-secondary" href="#approach">See how it works</a></div><div className="landing-proof"><span><ShieldCheck size={15} /> Backend-authoritative decisions</span><span><Cpu size={15} /> Local inference path</span></div></div>
      <div className="landing-visual" aria-label="Diagram of a virtual source connected through two feeders to six modeled services"><div className="visual-topline"><span>VIRTUAL GRID / OVERVIEW</span><span><i /> SIMULATION READY</span></div><div className="visual-source"><Zap size={17} /><span><b>MODELED SOURCE</b><small>14,000 W available</small></span><div className="source-meter"><i /></div></div><div className="visual-links"><div /></div><div className="visual-feeders"><div><span>FEEDER A</span><b>6,000 W</b></div><div><span>FEEDER B</span><b>8,000 W</b></div></div><div className="visual-services">{['ESSENTIAL LIGHTING','EMERGENCY LIGHT','WATER PUMP','CLASSROOM 01','CLASSROOM 02','CLASSROOM 03'].map((label,index)=><div className={index<2?'critical-node':''} key={label}><i /><span>{label}</span><b>{index<2?'CRITICAL':index===2?'POLICY RANKED':'EVIDENCE LED'}</b></div>)}</div><div className="visual-foot"><span><i className="cyan-dot" /> MODELLED ACTIVE</span><span><i className="amber-dot" /> ROOM EVIDENCE</span></div></div>
    </section>
    <section id="approach" className="landing-approach"><div className="section-overline">A CLEAR DECISION PATH</div><h2>Evidence in. Constraints stay visible.</h2><div className="approach-grid"><article><span>01</span><Activity size={20} /><h3>Observe</h3><p>Replay recorded office observations as virtual room evidence, with source and freshness shown.</p></article><article><span>02</span><BookOpen size={20} /><h3>Estimate activity</h3><p>A local model produces an activity state and reason. Missing or uncertain evidence stays unknown.</p></article><article><span>03</span><ShieldCheck size={20} /><h3>Allocate safely</h3><p>A constrained policy ranks eligible services while respecting source and feeder limits.</p></article></div></section>
    <section id="scope" className="landing-scope"><div><div className="section-overline">DEMO SCOPE</div><h2>Software simulation.<br /><em>Hardware disconnected.</em></h2></div><p>Source capacity, feeders, room activity and served loads are modeled. Recorded observations come from office occupancy data, replayed into virtual classrooms. The console reports modeled allocation, not physical power delivery or hardware acknowledgement.</p></section>
    <footer className="landing-footer"><Link to="/" className="landing-brand"><span><Activity size={17} /></span><b>BLACKOUT <i>MESH</i></b></Link><span>Research prototype · not for operational power control</span><Link to="/demo">Open command center <ArrowRight size={14} /></Link></footer>
  </main>;
}
