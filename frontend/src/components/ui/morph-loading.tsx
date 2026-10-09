import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export const MorphLoading = ({ className }: { className?: string }) => {
  return (
    <div className={cn("flex items-center justify-center space-x-2", className)}>
      {[0, 1, 2].map((index) => (
        <motion.div
          key={index}
          className="h-4 w-4 rounded-full bg-primary"
          animate={{
            scale: [1, 1.5, 1],
            opacity: [0.5, 1, 0.5],
            borderRadius: ["50%", "20%", "50%"],
          }}
          transition={{
            duration: 1,
            repeat: Infinity,
            delay: index * 0.2,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
};
