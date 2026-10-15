import { motion, useReducedMotion } from "framer-motion";

type SplitWordsProps = {
  text: string;
  className?: string;
  emphasis?: string[];
  emphasisClassName?: string;
  delay?: number;
};

export function SplitWords({
  text,
  className,
  emphasis = [],
  emphasisClassName = "font-display italic",
  delay = 0,
}: SplitWordsProps) {
  const reduceMotion = useReducedMotion();

  return (
    <span className={className} aria-label={text}>
      {text.split(" ").map((word, index) => (
        <span
          className="mr-[0.22em] inline-block overflow-hidden align-bottom"
          key={`${word}-${index}`}
        >
          <motion.span
            aria-hidden="true"
            className={
              emphasis.includes(word.replace(/[^a-zA-Z]/g, ""))
                ? `inline-block ${emphasisClassName}`
                : "inline-block"
            }
            initial={{ opacity: 0, y: "105%" }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: reduceMotion ? 0.2 : 0.8,
              delay: reduceMotion ? delay : delay + index * 0.06,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            {word}
          </motion.span>
        </span>
      ))}
    </span>
  );
}
