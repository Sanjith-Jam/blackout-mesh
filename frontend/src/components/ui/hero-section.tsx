import { AnimatedText } from "./animated-text";
import { Link } from 'react-router-dom';

export function HeroSection() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-transparent px-4 py-24 text-center">
      {/* Circuit background can go here as an absolute div */}
      <div className="absolute inset-0 z-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-primary/20 via-background to-background"></div>
      
      <div className="relative z-10 mx-auto max-w-4xl space-y-8">
        <AnimatedText
          text="Navigate a City Power Outage with Blackout Mesh"
          className="text-5xl font-extrabold tracking-tight sm:text-7xl lg:text-8xl text-foreground"
        />
        
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground sm:text-xl">
          Predictive AI for demand warnings, an interactive city grid, and guided outage recovery.
          Simulated power, explainable decisions, and real-time ESP32 status when connected.
        </p>
        <Link to="/demo" className="inline-block rounded-full bg-brand-sand px-8 py-3 font-semibold text-gray-900 focus-ring">Explore the city grid</Link>
        <p className="text-sm text-muted-foreground">Demand forecasts are trained on synthetic sessions. Physical hardware acceptance is pending.</p>

      </div>
    </div>
  );
}
