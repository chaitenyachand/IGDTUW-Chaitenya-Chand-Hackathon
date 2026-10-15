import { motion, useReducedMotion } from "framer-motion";
import { FileCheck2, Fingerprint, Gauge, ScanSearch, ShieldCheck, UserCheck } from "lucide-react";
import { useRef, type PointerEvent } from "react";

const principles = [
  {
    title: "Explainable signals",
    icon: ScanSearch,
    detail: "Trace the signal back to what prompted it.",
  },
  {
    title: "Calibrated shocks",
    icon: Gauge,
    detail: "Inspect the assumptions behind each scenario.",
  },
  { title: "Source integrity", icon: Fingerprint, detail: "Keep the underlying source in view." },
  { title: "Model transparency", icon: ShieldCheck, detail: "See how the assessment takes shape." },
  {
    title: "Full audit trail",
    icon: FileCheck2,
    detail: "Follow each decision from event to action.",
  },
  { title: "Human approval", icon: UserCheck, detail: "Keep the final decision in human hands." },
];

export function TrustGrid() {
  const grid = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const bounds = grid.current?.getBoundingClientRect();
    if (!bounds || reduceMotion) return;
    grid.current?.style.setProperty("--spot-x", `${event.clientX - bounds.left}px`);
    grid.current?.style.setProperty("--spot-y", `${event.clientY - bounds.top}px`);
  };
  return (
    <section id="trust" className="bg-paper py-24 text-foreground lg:py-36">
      <div className="mx-auto max-w-[1500px] px-5 lg:px-10">
        <p className="font-mono text-xs uppercase tracking-label text-primary">
          Built for scrutiny
        </p>
        <h2 className="mt-6 max-w-3xl font-display text-section leading-none">
          Trust is in the <em className="text-primary">details.</em>
        </h2>
        <div
          ref={grid}
          onPointerMove={move}
          className="trust-grid relative mt-16 grid gap-px overflow-hidden border border-hairline bg-hairline md:grid-cols-2 lg:grid-cols-3"
        >
          {principles.map(({ title, detail, icon: Icon }, index) => (
            <motion.article
              key={title}
              initial={{ opacity: 0, y: 22 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{
                duration: reduceMotion ? 0.2 : 0.7,
                delay: reduceMotion ? 0 : index * 0.08,
                ease: [0.22, 1, 0.36, 1],
              }}
              className="trust-cell relative flex min-h-[240px] flex-col justify-between bg-paper p-7 lg:min-h-[290px] lg:p-9"
            >
              <Icon className="size-7 text-primary" strokeWidth={1.25} aria-hidden="true" />
              <div>
                <h3 className="font-display text-3xl lg:text-4xl">{title}</h3>
                <p className="mt-3 max-w-xs text-sm text-secondary-foreground">{detail}</p>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}
