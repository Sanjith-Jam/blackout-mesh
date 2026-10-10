import { AnimatedText } from "./animated-text";
import { Link } from 'react-router-dom';

export function HeroSection() {
  return (
    <div className="relative flex flex-col items-center overflow-hidden bg-transparent px-4 pt-28 pb-20 text-center">
      <div className="relative z-10 mx-auto max-w-4xl space-y-7">
        <p className="type-eyebrow text-muted-foreground">Offline outage decision demo · simulated power</p>
        <AnimatedText
          text="Decide what stays on when the power runs short."
          className="hero-heading text-foreground"
        />
        <p className="mx-auto max-w-2xl text-lg leading-relaxed text-muted-foreground">
          Blackout Mesh keeps critical hospital circuits and classroom essentials on, ranks everything else by observed
          use, and gives every cut a one-sentence reason. Power is simulated; the ESP32 card reader and LEDs are real when connected.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link to="/demo" className="inline-block rounded-full bg-gray-900 px-7 py-3 font-medium text-white focus-ring">Open the city demo</Link>
          <Link to="/hospital" className="inline-block rounded-full border border-gray-300 bg-white px-7 py-3 font-medium text-gray-900 focus-ring">See fault diagnosis</Link>
        </div>
      </div>
    </div>
  );
}
