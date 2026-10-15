import { useRef } from "react";

import { useStoryScene } from "./story-motion";

const shocks = [
  { label: "Rates shock", change: "−8", start: 100, end: 92 },
  { label: "Equity shock", change: "−14", start: 92, end: 78 },
  { label: "Spread widening", change: "−6", start: 78, end: 72 },
];

function Waterfall({ animated = false }: { animated?: boolean }) {
  return (
    <div className="relative w-full max-w-[730px] border-t border-paper/20 pt-5">
      <div className="mb-10 flex items-center justify-between font-mono text-[10px] uppercase tracking-label text-paper/55">
        <span>Illustrative portfolio value</span>
        <span>Sample scenario</span>
      </div>
      <div className="grid h-[350px] grid-cols-5 items-end gap-2 sm:gap-5">
        <div className="flex h-full flex-col justify-end">
          <span className="mb-3 font-mono text-xl tabular-nums text-paper sm:text-3xl">100</span>
          <div className="h-[72%] bg-paper/80" />
          <span className="mt-4 min-h-10 font-mono text-[9px] uppercase text-paper/65 sm:text-[10px]">
            Starting
            <br />
            value
          </span>
        </div>
        {shocks.map((shock, index) => (
          <div key={shock.label} className="flex h-full flex-col justify-end">
            <span
              data-stress-number={animated ? "" : undefined}
              data-final={shock.end}
              className="mb-3 font-mono text-xl tabular-nums text-ember sm:text-3xl"
              style={animated && index > 0 ? { opacity: 0 } : undefined}
            >
              {animated ? shock.start : shock.end}
            </span>
            <div className="relative h-[72%] border-l border-dashed border-paper/20">
              <div
                data-stress-drop={animated ? "" : undefined}
                className="absolute left-0 right-0 bg-primary"
                style={{
                  top: `${100 - shock.start}%`,
                  height: animated ? 0 : `${shock.start - shock.end}%`,
                }}
                data-height={`${shock.start - shock.end}%`}
              />
              <span
                className="absolute left-2 font-mono text-[10px] text-ember"
                style={{ top: `${100 - shock.end + 3}%` }}
              >
                {shock.change}
              </span>
            </div>
            <span className="mt-4 min-h-10 font-mono text-[9px] uppercase leading-snug text-paper/65 sm:text-[10px]">
              {shock.label}
            </span>
          </div>
        ))}
        <div className="flex h-full flex-col justify-end">
          <span
            data-stress-result={animated ? "" : undefined}
            className="mb-3 font-mono text-xl tabular-nums text-paper sm:text-3xl"
            style={animated ? { opacity: 0 } : undefined}
          >
            {animated ? "100" : "72"}
          </span>
          <div
            data-stress-final={animated ? "" : undefined}
            className="bg-ember"
            style={{ height: animated ? "72%" : "51.84%", opacity: animated ? 0 : 1 }}
          />
          <span className="mt-4 min-h-10 font-mono text-[9px] uppercase text-paper/65 sm:text-[10px]">
            Stressed
            <br />
            value
          </span>
        </div>
      </div>
      <div className="absolute bottom-[53px] left-0 right-0 border-t border-paper/20" />
    </div>
  );
}

export function StressLab() {
  const section = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  useStoryScene(section, 4, ({ gsap, root, priority }) => {
    const pinned = stage.current;
    if (!pinned) return;
    const drops = gsap.utils.toArray<HTMLElement>("[data-stress-drop]", pinned);
    const numbers = gsap.utils.toArray<HTMLElement>("[data-stress-number]", pinned);
    const final = pinned.querySelector("[data-stress-final]");
    const result = pinned.querySelector("[data-stress-result]");
    const glow = pinned.querySelector("[data-stress-glow]");
    if (drops.length !== 3 || numbers.length !== 3 || !final || !result || !glow) return;
    const timeline = gsap.timeline({
      scrollTrigger: {
        trigger: root,
        start: "top top",
        end: "+=200%",
        scrub: 0.6,
        pin: pinned,
        pinSpacing: true,
        invalidateOnRefresh: true,
        refreshPriority: priority,
      },
    });
    timeline.to(glow, { opacity: 0.8, scale: 1.35, duration: 3 }, 0);
    drops.forEach((drop, index) => {
      const number = numbers[index];
      const target = Number(number?.dataset["final"]);
      const height = drop.dataset["height"];
      if (!number || !Number.isFinite(target) || !height) return;
      if (index > 0)
        timeline.set(number, { textContent: shocks[index - 1]?.end ?? 100, opacity: 1 });
      timeline
        .to(drop, { height, duration: 0.65, ease: "power2.out" })
        .to(number, { textContent: target, snap: { textContent: 1 }, duration: 0.65 }, "<");
    });
    timeline
      .set([final, result], { opacity: 1 })
      .set(result, { textContent: 100 })
      .to(final, { height: "51.84%", duration: 0.7 })
      .to(result, { textContent: 72, snap: { textContent: 1 }, duration: 0.7 }, "<")
      .to({}, { duration: 0.3 });
  });

  const visual = (animated: boolean) => (
    <div className="mx-auto grid h-full w-full max-w-[1600px] items-center gap-14 px-5 lg:grid-cols-[.8fr_1.2fr] lg:px-10">
      <div className="relative z-10">
        <p className="font-mono text-xs uppercase tracking-label text-ember">Stress Lab / 05</p>
        <h2 className="mt-7 max-w-[650px] font-display text-section leading-[0.98]">
          See the impact <em className="text-ember">before</em> it lands.
        </h2>
      </div>
      <div className="relative z-10">
        <Waterfall animated={animated} />
      </div>
    </div>
  );
  return (
    <section
      ref={section}
      id="stress-lab"
      data-story-shell
      className="relative isolate overflow-hidden bg-ink text-paper"
    >
      <div ref={stage} data-story-stage="ink" className="motion-story-stage h-svh overflow-hidden">
        <div
          data-stress-glow
          className="stress-glow pointer-events-none absolute inset-0 opacity-20"
        />
        <div className="stress-particles pointer-events-none absolute inset-0" aria-hidden="true" />
        {visual(true)}
      </div>
      <div className="motion-story-fallback relative py-24">
        <div className="stress-glow pointer-events-none absolute inset-0 opacity-30" />
        {visual(false)}
      </div>
    </section>
  );
}
