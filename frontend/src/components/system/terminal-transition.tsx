import { Link, useNavigate } from "@tanstack/react-router";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import {
  createContext,
  useContext,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";

import { Magnetic } from "@/components/motion/magnetic";
import { Button } from "@/components/ui/button";

type TransitionContextValue = { open: (event: MouseEvent<HTMLAnchorElement>) => void };
const TransitionContext = createContext<TransitionContextValue | null>(null);

export function TerminalTransitionProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();
  const [origin, setOrigin] = useState<{ x: number; y: number } | null>(null);
  const [phase, setPhase] = useState<"cover" | "reveal">("cover");
  const busy = useRef(false);

  const open = (event: MouseEvent<HTMLAnchorElement>) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    if (reduceMotion) return;
    event.preventDefault();
    if (busy.current) return;
    busy.current = true;
    const rect = event.currentTarget.getBoundingClientRect();
    setOrigin({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
    setPhase("cover");
    window.setTimeout(() => {
      void navigate({ to: "/app" });
      window.scrollTo(0, 0);
      setPhase("reveal");
      window.setTimeout(() => {
        setOrigin(null);
        busy.current = false;
      }, 420);
    }, 720);
  };

  return (
    <TransitionContext.Provider value={{ open }}>
      {children}
      <AnimatePresence>
        {origin && (
          <motion.div
            aria-hidden="true"
            className="pointer-events-none fixed z-[120] rounded-full bg-primary"
            style={{
              width: "200vmax",
              height: "200vmax",
              left: origin.x,
              top: origin.y,
              x: "-50%",
              y: "-50%",
            }}
            initial={{ scale: 0, opacity: 1 }}
            animate={{ scale: 1, opacity: phase === "cover" ? 1 : 0 }}
            exit={{ opacity: 0 }}
            transition={
              phase === "cover"
                ? { scale: { duration: 0.72, ease: [0.22, 1, 0.36, 1] } }
                : { opacity: { duration: 0.38 } }
            }
          />
        )}
      </AnimatePresence>
    </TransitionContext.Provider>
  );
}

export function TerminalLink({ large = false }: { large?: boolean }) {
  const transition = useContext(TransitionContext);
  return (
    <Magnetic>
      <Button
        asChild
        size="lg"
        className={`${large ? "h-16 px-8 text-sm" : "h-12 px-6 text-xs"} rounded-none font-mono uppercase tracking-label shadow-none hover:bg-primary-hover`}
      >
        <Link to="/app" onClick={transition?.open}>
          Open Terminal <ArrowUpRight aria-hidden="true" />
        </Link>
      </Button>
    </Magnetic>
  );
}
