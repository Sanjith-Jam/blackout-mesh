import { AnimatedText } from "./animated-text";

export function HeroSection() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-transparent px-4 py-24 text-center">
      {/* Circuit background can go here as an absolute div */}
      <div className="absolute inset-0 z-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-primary/20 via-background to-background"></div>
      
      <div className="relative z-10 mx-auto max-w-4xl space-y-8">
        <AnimatedText
          text="Transforming Grid Resilience with Blackout Mesh"
          className="text-5xl font-extrabold tracking-tight sm:text-7xl lg:text-8xl text-foreground"
        />
        
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground sm:text-xl">
          An advanced decentralized grid management system. Navigate power outages seamlessly with real-time hardware monitoring, predictive AI, and interactive dashboards.
        </p>

      </div>
    </div>
  );
}
