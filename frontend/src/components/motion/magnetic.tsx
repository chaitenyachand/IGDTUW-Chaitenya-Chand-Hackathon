import { motion, useMotionValue, useReducedMotion, useSpring } from "framer-motion";
import type { MouseEvent, ReactNode } from "react";

export function Magnetic({ children }: { children: ReactNode }) {
  const reduceMotion = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 180, damping: 18, mass: 0.2 });
  const springY = useSpring(y, { stiffness: 180, damping: 18, mass: 0.2 });

  function move(event: MouseEvent<HTMLDivElement>) {
    if (reduceMotion) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    x.set((event.clientX - bounds.left - bounds.width / 2) * 0.18);
    y.set((event.clientY - bounds.top - bounds.height / 2) * 0.18);
  }

  function reset() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.div style={{ x: springX, y: springY }} onMouseMove={move} onMouseLeave={reset}>
      {children}
    </motion.div>
  );
}
