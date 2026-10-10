import { Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { SlideTabs } from '@/components/ui/slide-tabs';
import { motion, useScroll, useMotionValueEvent } from 'framer-motion';
import { useState } from 'react';

export function Header() {
  const { scrollY } = useScroll();
  const [hidden, setHidden] = useState(false);

  useMotionValueEvent(scrollY, "change", (latest) => {
    const previous = scrollY.getPrevious() ?? 0;
    if (latest > previous && latest > 100) {
      setHidden(true);
    } else {
      setHidden(false);
    }
  });

  return (
    <motion.header
      variants={{
        visible: { y: 0 },
        hidden: { y: "-100%" },
      }}
      animate={hidden ? "hidden" : "visible"}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="site-header sticky top-0 w-full z-50 grid grid-cols-[1fr_auto_1fr] items-center py-4 px-6 md:px-8 bg-vintage/80 backdrop-blur-md border-b border-gray-200/50"
    >
      <div className="flex items-center justify-start gap-2 text-brand-forest font-bold text-xl">
        <Activity className="text-brand-forest" />
        <Link to="/" className="inline-block">Blackout Mesh</Link>
      </div>
      
      <div className="flex justify-center w-full min-w-0">
        <SlideTabs tabs={[
          { label: "Overview", href: "/" },
          { label: "District", href: "/grid" },
          { label: "Hospital", href: "/hospital" },
          { label: "Classrooms", href: "/classrooms" }
        ]} />
      </div>
      
      <div className="flex justify-end">
        <Link to="/grid" className="inline-block px-5 py-2.5 bg-brand-sand hover:bg-brand-sand-dark text-gray-900 border border-brand-sand-dark/50 rounded-full font-medium transition-all active:scale-[0.97] focus-ring shadow-[4px_4px_0px_0px_rgba(0,0,0,0.05)] text-sm md:text-base">
          <span className="hidden sm:inline">Launch Demo</span>
          <span className="sm:hidden">Demo</span>
        </Link>
      </div>
    </motion.header>
  );
}
