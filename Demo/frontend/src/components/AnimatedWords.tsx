import { motion } from "framer-motion";

type AnimatedWordsProps = {
  text: string;
  startDelay?: number;
  stagger?: number;
  className?: string;
};

const easeOut = [0.16, 1, 0.3, 1] as const;

/** Splits text into words that fade/rise/settle in one-by-one instead of arriving as a single flat block. */
export function AnimatedWords({ text, startDelay = 0, stagger = 0.045, className = "" }: AnimatedWordsProps) {
  const words = text.split(" ");
  return (
    <span className={className}>
      {words.map((word, i) => (
        <span key={`${word}-${i}`} className="inline-block overflow-hidden pb-1 align-bottom">
          <motion.span
            className="inline-block"
            initial={{ y: "110%", rotate: 4 }}
            animate={{ y: "0%", rotate: 0 }}
            transition={{
              duration: 0.65,
              delay: startDelay + i * stagger,
              ease: easeOut,
            }}
          >
            {word}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </span>
  );
}
