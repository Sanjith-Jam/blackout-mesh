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
    <div className="relative flex w-full max-w-fit items-center rounded-full bg-gray-100/60 p-1 backdrop-blur-sm border border-gray-200/50">
      {tabs.map((tab) => {
        const isActive = currentPath === tab.href || (currentPath === '/' && tab.href === '/');
        
        return (
          <div key={tab.label} className="relative z-10 flex">
            {tab.isHash ? (
              <a
                href={tab.href}
                className={cn(
                  "px-6 py-2 text-sm font-medium transition-colors block",
                  isActive ? "text-gray-900" : "text-gray-500 hover:text-gray-700"
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="slide-tab"
                    className="absolute inset-0 -z-10 rounded-full bg-[#e8dcc4] shadow-sm border border-[#d4c5ab]/50"
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                )}
                {tab.label}
              </a>
            ) : (
              <Link
                to={tab.href}
                className={cn(
                  "px-6 py-2 text-sm font-medium transition-colors block",
                  isActive ? "text-gray-900" : "text-gray-500 hover:text-gray-700"
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="slide-tab"
                    className="absolute inset-0 -z-10 rounded-full bg-[#e8dcc4] shadow-sm border border-[#d4c5ab]/50"
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
