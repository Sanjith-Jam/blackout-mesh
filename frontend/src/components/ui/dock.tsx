import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import React from "react";

interface DockProps {
  children: React.ReactNode;
  className?: string;
}

export function Dock({ children, className }: DockProps) {
  return (
    <div className={cn("fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 rounded-2xl bg-background/80 p-4 shadow-xl backdrop-blur-lg border border-border", className)}>
      {children}
    </div>
  );
}

export function DockItem({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick?: () => void }) {
  return (
    <motion.button
      whileHover={{ scale: 1.2, y: -10 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className="group relative flex flex-col items-center justify-center rounded-xl p-2 transition-all hover:bg-muted"
    >
      <div className="text-foreground">{icon}</div>
      <span className="absolute -top-8 hidden rounded-md bg-foreground px-2 py-1 text-xs text-background group-hover:block">
        {label}
      </span>
    </motion.button>
  );
}
