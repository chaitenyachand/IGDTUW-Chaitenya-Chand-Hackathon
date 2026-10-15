import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

const KEY = "sentinel:preloaded";
const WORD = "SENTINEL";

/** Session-once intro. Calls onDone when the hero should start animating. */
export function Preloader({ onDone }: { onDone: () => void }) {
  const [visible, setVisible] = useState(true);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (sessionStorage.getItem(KEY)) {
      setVisible(false);
      onDone();
      return;
    }
    document.documentElement.style.overflow = "hidden";
    const total = reduceMotion ? 600 : 1800;
    const t = window.setTimeout(() => {
      sessionStorage.setItem(KEY, "1");
      setVisible(false);
      document.documentElement.style.overflow = "";
      onDone();
    }, total);
    return () => {
      window.clearTimeout(t);
      document.documentElement.style.overflow = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AnimatePresence>
      {visible ? (
        <motion.div
          key="preloader"
          className="fixed inset-0 z-[100] flex items-center justify-center bg-paper"
          exit={reduceMotion ? { opacity: 0 } : { y: "-100%" }}
          transition={{ duration: reduceMotion ? 0.3 : 0.8, ease: [0.76, 0, 0.24, 1] }}
          aria-hidden="true"
        >
          <div className="relative">
            <div className="flex font-display text-[clamp(3rem,10vw,7.5rem)] leading-none text-foreground">
              {WORD.split("").map((ch, i) => (
                <motion.span
                  key={i}
                  initial={{ opacity: 0, y: "40%" }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    duration: 0.5,
                    delay: reduceMotion ? 0 : 0.1 + i * 0.07,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                >
                  {ch}
                </motion.span>
              ))}
            </div>
            <motion.div
              className="mt-4 h-px origin-left bg-primary"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{
                duration: reduceMotion ? 0.2 : 0.7,
                delay: reduceMotion ? 0 : 0.8,
                ease: [0.65, 0, 0.35, 1],
              }}
            />
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
