import { useEffect, useRef, useState } from "react";
import { useRouterState } from "@tanstack/react-router";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

/** Crimson wipe when entering the terminal from outside it. Moves inside /app use the page fade instead. */
export function AppRouteWipe() {
  const path = useRouterState({ select: (state) => state.location.pathname });
  const reduceMotion = useReducedMotion();
  const prev = useRef<string | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const entering = path.startsWith("/app") && !(prev.current ?? "").startsWith("/app");
    prev.current = path;
    if (!entering) return;
    setPlaying(true);
    const t = setTimeout(() => setPlaying(false), 450);
    return () => clearTimeout(t);
  }, [path]);

  return (
    <AnimatePresence>
      {playing && !reduceMotion && (
        <motion.div
          key="wipe"
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 z-[110] bg-primary"
          initial={{ clipPath: "circle(150% at 50% 50%)", opacity: 0.42 }}
          animate={{ clipPath: "circle(0% at 50% 50%)", opacity: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
        />
      )}
    </AnimatePresence>
  );
}
