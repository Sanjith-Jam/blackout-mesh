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
      className="sticky top-0 w-full z-50 flex justify-between items-center p-6 bg-background/50 backdrop-blur-md border-b border-border"
    >
      <div className="flex items-center gap-2 text-primary font-bold text-xl">
        <Activity className="brand-icon" />
        <span className="brand-name">PriorityGrid</span>
      </div>
      
      <SlideTabs tabs={[
        { label: "Overview", href: "/" },
        { label: "Hospital", href: "/hospital" },
        { label: "Classrooms", href: "/classrooms" }
      ]} />
      
      <div>
        <Link to="/demo" className="inline-block px-5 py-2.5 bg-[#e8dcc4] hover:bg-[#d4c5ab] text-gray-900 border border-[#d4c5ab]/50 rounded-full font-medium transition-colors shadow-sm">Launch Demo</Link>
      </div>
    </motion.header>
  );
}
