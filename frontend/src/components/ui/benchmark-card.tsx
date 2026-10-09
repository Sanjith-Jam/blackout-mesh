import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

export function BenchmarkCard({ title, stats }: { title: string; stats: { label: string; value: number }[] }) {
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-6 shadow-sm">
      <h3 className="text-xl font-semibold text-card-foreground">{title}</h3>
      <div className="flex flex-col gap-3">
        {stats.map((stat, i) => (
          <div key={i} className="flex items-center gap-4">
            <span className="w-24 text-sm text-muted-foreground">{stat.label}</span>
            <div className="relative h-4 flex-1 overflow-hidden rounded-full bg-secondary">
              <motion.div
                initial={{ width: 0 }}
                whileInView={{ width: `${stat.value}%` }}
                transition={{ duration: 1, delay: i * 0.2 }}
                className={cn("absolute inset-y-0 left-0 bg-primary", stat.value > 80 ? "bg-emerald-500" : "bg-primary")}
              />
            </div>
            <span className="w-12 text-right text-sm font-medium">{stat.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
