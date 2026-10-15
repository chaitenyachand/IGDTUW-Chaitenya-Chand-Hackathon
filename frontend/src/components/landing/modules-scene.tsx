import { useRef, type PointerEvent } from "react";

import { useStoryScene } from "./story-motion";

function ModuleCard({
  kind,
  title,
  index,
  stacked = false,
}: {
  kind: "area" | "bars";
  title: string;
  index: string;
  stacked?: boolean;
}) {
  const card = useRef<HTMLElement>(null);
  const onMove = (event: PointerEvent<HTMLElement>) => {
    if (!card.current || stacked || window.matchMedia("(prefers-reduced-motion: reduce)").matches)
      return;
    const rect = card.current.getBoundingClientRect();
    const rx = ((event.clientY - rect.top) / rect.height - 0.5) * -5;
    const ry = ((event.clientX - rect.left) / rect.width - 0.5) * 7;
    card.current.style.transform = `perspective(1200px) rotateX(${rx}deg) rotateY(${ry}deg)`;
  };
  const reset = () => {
    if (card.current)
      card.current.style.transform = "perspective(1200px) rotateX(0deg) rotateY(0deg)";
  };
  const size = stacked
    ? "w-full min-h-[440px] gap-10"
    : "h-[min(62svh,620px)] min-h-[400px] w-[min(76vw,1040px)] shrink-0";
  return (
    <article
      ref={card}
      data-module-card
      onPointerMove={onMove}
      onPointerLeave={reset}
      className={`${size} flex flex-col justify-between border border-hairline bg-paper p-7 text-foreground transition-transform duration-300 lg:p-10`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="font-mono text-xs text-primary">{index}</span>
          <h3 className="mt-4 font-display text-5xl leading-none lg:text-7xl">{title}</h3>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-label text-muted-foreground">
          Portfolio module
        </span>
      </div>
      {kind === "area" ? (
        <svg
          viewBox="0 0 700 260"
          className="max-h-[38%] w-full"
          preserveAspectRatio="none"
          aria-label="Adaptive index stacked area chart"
          role="img"
        >
          <path
            data-chart-shape
            d="M0 210 C100 190 150 202 240 165 S390 188 480 132 S610 102 700 72 L700 260 L0 260Z"
            fill="var(--hairline)"
          />
          <path
            data-chart-shape
            d="M0 225 C110 215 170 175 250 185 S390 140 480 148 S610 95 700 112 L700 260 L0 260Z"
            fill="var(--positive)"
            opacity=".78"
          />
          <path
            data-chart-shape
            d="M0 244 C110 232 180 218 255 205 S390 190 485 168 S610 145 700 130 L700 260 L0 260Z"
            fill="var(--primary)"
            opacity=".88"
          />
        </svg>
      ) : (
        <div className="grid gap-6">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-label text-muted-foreground">
              Before
            </span>
            <div className="mt-3 grid h-20 grid-cols-5 items-end gap-3 xl:h-24">
              {[78, 52, 90, 42, 66].map((h, i) => (
                <span key={i} data-chart-bar className="bg-hairline" style={{ height: `${h}%` }} />
              ))}
            </div>
          </div>
          <div>
            <span className="font-mono text-[10px] uppercase tracking-label text-primary">
              After stress
            </span>
            <div className="mt-3 grid h-20 grid-cols-5 items-end gap-3 xl:h-24">
              {[48, 38, 61, 22, 54].map((h, i) => (
                <span key={i} data-chart-bar className="bg-primary" style={{ height: `${h}%` }} />
              ))}
            </div>
          </div>
        </div>
      )}
      <div className="flex justify-between border-t border-hairline pt-4 font-mono text-[10px] uppercase tracking-label text-muted-foreground">
        <span>{kind === "area" ? "Risk-adjusted allocation" : "Scenario: supply shock"}</span>
        <span>Sample data</span>
      </div>
    </article>
  );
}

export function ModulesScene() {
  const section = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);

  useStoryScene(section, 3, ({ gsap, ScrollTrigger, root, priority }) => {
    const scope = stage.current;
    const rail = track.current;
    if (!scope || !rail) return;
    const [first, second] = gsap.utils.toArray<HTMLElement>("[data-module-card]", scope);
    if (!first || !second) return;
    const replay = (card: HTMLElement) =>
      gsap.timeline({ paused: true }).fromTo(
        card.querySelectorAll("[data-chart-shape], [data-chart-bar]"),
        { scaleY: 0 },
        {
          scaleY: 1,
          transformOrigin: "bottom",
          stagger: 0.08,
          duration: 0.8,
          ease: "power3.out",
        },
      );
    const firstChart = replay(first);
    const secondChart = replay(second);
    const tween = gsap.to(rail, {
      x: () => -Math.max(0, rail.scrollWidth - window.innerWidth + 80),
      ease: "none",
      scrollTrigger: {
        trigger: root,
        start: "top top",
        end: "+=240%",
        scrub: 0.6,
        pin: scope,
        pinSpacing: true,
        invalidateOnRefresh: true,
        refreshPriority: priority,
      },
    });
    // The first card is visible before the rail moves, so replay it as the scene arrives.
    ScrollTrigger.create({
      trigger: root,
      start: "top 55%",
      refreshPriority: priority - 0.5,
      onEnter: () => firstChart.restart(),
      onEnterBack: () => firstChart.restart(),
      onLeaveBack: () => firstChart.pause(0),
    });
    ScrollTrigger.create({
      trigger: second,
      containerAnimation: tween,
      start: "left 85%",
      onEnter: () => secondChart.restart(),
      onEnterBack: () => secondChart.restart(),
      onLeaveBack: () => secondChart.pause(0),
    });
  });

  return (
    <section
      ref={section}
      id="modules"
      data-story-shell
      className="relative isolate overflow-hidden bg-ink text-primary-foreground"
    >
      <div ref={stage} data-story-stage="ink" className="motion-story-stage h-svh overflow-hidden">
        <div className="flex h-full flex-col justify-center">
          <div className="mb-8 flex items-end justify-between px-10">
            <div>
              <p className="font-mono text-xs uppercase tracking-label text-primary">Modules</p>
              <h2 className="mt-4 font-display text-6xl leading-none">Built to respond.</h2>
            </div>
            <p className="font-mono text-[10px] uppercase tracking-label text-muted-foreground">
              Scroll to explore
            </p>
          </div>
          <div ref={track} className="flex w-max gap-8 pl-[22vw] pr-20 will-change-transform">
            <ModuleCard index="01" title="Adaptive Index" kind="area" />
            <ModuleCard index="02" title="Stress Lab" kind="bars" />
          </div>
        </div>
      </div>
      <div className="motion-story-fallback px-5 py-24">
        <p className="font-mono text-xs uppercase tracking-label text-primary">Modules</p>
        <h2 className="mt-5 font-display text-section">Built to respond.</h2>
        <div className="mt-12 grid gap-6">
          <ModuleCard index="01" title="Adaptive Index" kind="area" stacked />
          <ModuleCard index="02" title="Stress Lab" kind="bars" stacked />
        </div>
      </div>
    </section>
  );
}
