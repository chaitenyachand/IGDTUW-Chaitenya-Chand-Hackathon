import { useEffect, useRef } from "react";
import { useRouterState } from "@tanstack/react-router";

/**
 * Small crimson dot that follows the pointer on the public landing page.
 * It is disabled on touch devices, with reduced motion, and inside the
 * terminal (/app/*) where the normal system cursor is used.
 */
export function CustomCursor() {
  const ref = useRef<HTMLDivElement>(null);
  const path = useRouterState({ select: (s) => s.location.pathname });
  const inTerminal = path.startsWith("/app");

  useEffect(() => {
    if (inTerminal) return;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (coarse || reduced) return;
    const el = ref.current;
    if (!el) return;
    let x = -100;
    let y = -100;
    let cx = x;
    let cy = y;
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      x = e.clientX;
      y = e.clientY;
      el.style.opacity = "1";
      const t = e.target as HTMLElement | null;
      const interactive = !!t?.closest?.("a, button, [role='button'], input, textarea, select");
      el.style.width = el.style.height = interactive ? "36px" : "10px";
    };
    const onLeave = () => {
      el.style.opacity = "0";
    };
    const tick = () => {
      cx += (x - cx) * 0.22;
      cy += (y - cy) * 0.22;
      el.style.transform = `translate3d(${cx}px, ${cy}px, 0) translate(-50%, -50%)`;
      raf = requestAnimationFrame(tick);
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, [inTerminal]);

  if (inTerminal) return null;
  return (
    <div
      ref={ref}
      aria-hidden="true"
      className="pointer-events-none fixed left-0 top-0 z-[120] rounded-full bg-primary/80 mix-blend-multiply"
      style={{
        width: 10,
        height: 10,
        opacity: 0,
        transition: "width .25s, height .25s, opacity .25s",
      }}
    />
  );
}
