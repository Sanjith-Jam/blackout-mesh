import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export const AnimatedText = ({
  text,
  className,
}: {
  text: string;
  className?: string;
}) => {
  const words = text.split(" ");

  return (
    <motion.div
      className={cn("flex flex-wrap items-center justify-center gap-2", className)}
      initial="hidden"
      animate="visible"
      variants={{
        visible: { transition: { staggerChildren: 0.1 } },
        hidden: {},
      }}
    >
      {words.map((word, i) => (
        <motion.span
          key={i}
          className="inline-block"
          variants={{
            hidden: { opacity: 0, y: 20 },
            visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
          }}
        >
          {word}
        </motion.span>
      ))}
    </motion.div>
  );
};
