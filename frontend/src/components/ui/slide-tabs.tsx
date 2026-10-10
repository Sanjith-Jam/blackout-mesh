import { motion } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

export interface TabItem {
  label: string;
  href: string;
  isHash?: boolean;
}

export function SlideTabs({ tabs }: { tabs: TabItem[] }) {
  const location = useLocation();
  const currentPath = location.pathname + location.hash;

  return (
    <div className="relative flex w-full max-w-full items-center rounded-full bg-gray-100/60 p-1 backdrop-blur-sm border border-gray-200/50 overflow-x-auto whitespace-nowrap scrollbar-hide">
      {tabs.map((tab) => {
        const isActive = currentPath === tab.href || (currentPath === '/' && tab.href === '/');
        
        return (
          <div key={tab.label} className="relative z-10 flex shrink-0">
            {tab.isHash ? (
              <a
                href={tab.href}
                className={cn(
                  "px-6 py-2 text-sm font-medium transition-colors block focus-ring rounded-full",
                  isActive ? "text-gray-900" : "text-gray-500 hover:text-gray-700"
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="slide-tab"
                    className="absolute inset-0 -z-10 rounded-full bg-brand-sand shadow-[4px_4px_0px_0px_rgba(0,0,0,0.05)] border border-brand-sand-dark/50"
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                )}
                {tab.label}
              </a>
            ) : (
              <Link
                to={tab.href}
                className={cn(
                  "px-6 py-2 text-sm font-medium transition-colors block focus-ring rounded-full",
                  isActive ? "text-gray-900" : "text-gray-500 hover:text-gray-700"
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="slide-tab"
                    className="absolute inset-0 -z-10 rounded-full bg-brand-sand shadow-[4px_4px_0px_0px_rgba(0,0,0,0.05)] border border-brand-sand-dark/50"
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                )}
                {tab.label}
              </Link>
            )}
          </div>
        );
      })}
    </div>
  );
}
