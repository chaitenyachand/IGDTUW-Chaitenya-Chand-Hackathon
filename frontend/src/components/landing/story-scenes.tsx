import { useRef } from "react";

import { useStoryScene } from "./story-motion";

const headlines = [
  { source: "News", text: "Shipping restrictions widen across strategic trade corridor" },
  { source: "Social", text: "Port queues extend as carriers reroute high-value cargo" },
  { source: "News", text: "Insurers lift war-risk premiums for regional crossings" },
  { source: "Social", text: "Manufacturers flag a two-week component delay" },
];

const analogs = [
  "M0 96 C70 94 95 58 150 65 S230 102 300 64 S390 42 470 56 S550 33 620 45",
  "M0 96 C62 91 112 71 164 78 S250 118 314 76 S398 51 470 70 S554 42 620 59",
  "M0 96 C75 101 120 83 175 70 S250 86 310 69 S388 75 450 55 S540 62 620 47",
  "M0 96 C55 86 110 54 170 73 S252 105 320 86 S402 44 458 61 S542 47 620 53",
  "M0 96 C64 97 104 105 164 84 S246 57 306 72 S390 93 460 67 S548 55 620 66",
  "M0 96 C75 88 121 63 175 66 S254 92 315 57 S405 60 468 44 S548 31 620 39",
  "M0 96 C68 105 113 88 170 91 S255 73 314 80 S400 62 468 72 S552 45 620 50",
  "M0 96 C58 94 108 70 165 76 S252 84 312 66 S396 40 462 50 S550 38 620 45",
  "M0 96 C69 91 118 74 174 80 S252 99 318 74 S397 54 461 64 S547 52 620 57",
  "M0 96 C71 99 116 89 171 74 S252 69 311 77 S394 70 462 58 S548 40 620 48",
];

function SourceCards({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? "grid gap-3" : "relative h-[390px]"}>
      {headlines.map((item, index) => (
        <article
          key={item.text}
          data-source-card={compact ? undefined : ""}
          className={
            compact
              ? "border border-hairline bg-paper p-4"
              : "absolute left-1/2 top-1/2 w-[min(92%,520px)] border border-hairline bg-paper p-5 shadow-sm"
          }
          style={compact ? undefined : { zIndex: headlines.length - index }}
        >
          <span className="font-mono text-[10px] uppercase tracking-label text-primary">
            {item.source}
          </span>
          <p className="mt-2 max-w-md text-base font-medium leading-snug">{item.text}</p>
        </article>
      ))}
    </div>
  );
}

function Metrics() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div data-metric className="border border-hairline bg-paper p-4">
        <span className="font-mono text-[10px] uppercase tracking-label text-muted-foreground">
          Sentiment
        </span>
        <strong
          data-value="-0.74"
          className="mt-5 block font-mono text-3xl font-normal tabular-nums"
        >
          -0.74
        </strong>
      </div>
      <div data-metric className="border border-hairline bg-paper p-4">
        <span className="font-mono text-[10px] uppercase tracking-label text-muted-foreground">
          Event class
        </span>
        <strong className="mt-5 block font-mono text-sm font-medium uppercase text-primary">
          Supply shock
        </strong>
      </div>
      <div data-metric className="border border-hairline bg-paper p-4">
        <span className="font-mono text-[10px] uppercase tracking-label text-muted-foreground">
          Impact
        </span>
        <strong data-value="8.4" className="mt-5 block font-mono text-3xl font-normal tabular-nums">
          8.4
        </strong>
      </div>
    </div>
  );
}

function Portfolio({ animated = false }: { animated?: boolean }) {
  const weights = [
    ["Equities", "52%", "bg-ink"],
    ["Credit", "24%", "bg-primary"],
    ["Hedges", "16%", "bg-positive"],
    ["Cash", "8%", "bg-hairline"],
  ];
  return (
    <div>
      <div className="flex h-16 overflow-hidden border border-hairline bg-surface">
        {weights.map(([label, width, color], index) => (
          <div
            key={label}
            data-weight={animated ? "" : undefined}
            data-target={width}
            className={`${color} flex min-w-0 items-center justify-center overflow-hidden`}
            style={{ width: animated ? ["63%", "21%", "9%", "7%"][index] : width }}
          >
            <span
              className={`font-mono text-[10px] ${index < 3 ? "text-primary-foreground" : "text-foreground"}`}
            >
              {label}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
        {weights.map(([label, width, color]) => (
          <span key={label} className="font-mono text-[10px] text-muted-foreground">
            <i className={`mr-1.5 inline-block size-2 ${color}`} />
            {label} {width}
          </span>
        ))}
      </div>
      <p
        data-log={animated ? "" : undefined}
        className="mt-8 overflow-hidden whitespace-nowrap border-l-2 border-primary pl-3 font-mono text-xs text-primary"
      >
        09:42:18 — Rebalanced · risk budget restored
      </p>
    </div>
  );
}

export function IntelligenceStory() {
  const section = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);

  useStoryScene(section, 1, ({ gsap, root, priority }) => {
    const scope = stage.current;
    if (!scope) return;
    const cards = gsap.utils.toArray<HTMLElement>("[data-source-card]", scope);
    const panels = gsap.utils.toArray<HTMLElement>("[data-story-panel]", scope);
    const titles = gsap.utils.toArray<HTMLElement>("[data-story-title]", scope);
    const metrics = gsap.utils.toArray<HTMLElement>("[data-metric]", scope);
    const log = scope.querySelector<HTMLElement>("[data-log]");
    const highlights = gsap.utils.toArray<HTMLElement>("[data-highlight]", scope);
    const weights = gsap.utils.toArray<HTMLElement>("[data-weight]", scope);
    const dots = gsap.utils.toArray<HTMLElement>("[data-story-dot]", scope);
    const sentiment = scope.querySelector("[data-value='-0.74']");
    const impact = scope.querySelector("[data-value='8.4']");
    const [panelRead, panelUnderstand, panelAct] = panels;
    const [titleRead, titleUnderstand, titleAct] = titles;
    const [dotRead, dotUnderstand, dotAct] = dots;
    if (
      !panelRead ||
      !panelUnderstand ||
      !panelAct ||
      !titleRead ||
      !titleUnderstand ||
      !titleAct ||
      !dotRead ||
      !dotUnderstand ||
      !dotAct ||
      !log ||
      !sentiment ||
      !impact
    )
      return;
    gsap.set(panels.slice(1), { autoAlpha: 0 });
    gsap.set(titles.slice(1), { autoAlpha: 0, y: 22 });
    gsap.set(cards, { xPercent: -50, yPercent: -50 });
    cards.forEach((card, index) =>
      gsap.set(card, {
        x: index % 2 ? 420 : -420,
        y: (index - 1.5) * 72,
        rotate: index % 2 ? 4 : -4,
        opacity: 0,
      }),
    );
    gsap.set(metrics, { y: 24, opacity: 0 });
    gsap.set(log, { width: 0, opacity: 0 });
    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: root,
        start: "top top",
        end: "+=300%",
        scrub: 0.6,
        pin: scope,
        pinSpacing: true,
        invalidateOnRefresh: true,
        refreshPriority: priority,
      },
    });
    tl.to(cards, {
      x: 0,
      y: (index) => (index - 1.5) * 22,
      rotate: 0,
      opacity: 1,
      stagger: 0.05,
      duration: 1,
    })
      .to({}, { duration: 0.35 })
      .to([panelRead, titleRead], { autoAlpha: 0, y: -18, duration: 0.35 })
      .to([panelUnderstand, titleUnderstand], { autoAlpha: 1, y: 0, duration: 0.45 }, "<0.1")
      .to(dotRead, { scale: 0.65, opacity: 0.35 }, "<")
      .to(dotUnderstand, { scale: 1.5, opacity: 1 }, "<")
      .fromTo(
        highlights,
        { backgroundSize: "0% 100%" },
        { backgroundSize: "100% 100%", stagger: 0.12, duration: 0.65 },
      )
      .to(metrics, { y: 0, opacity: 1, stagger: 0.12, duration: 0.55 })
      .fromTo(
        sentiment,
        { textContent: -1 },
        { textContent: -0.74, snap: { textContent: 0.01 }, duration: 0.55 },
        "<",
      )
      .fromTo(
        impact,
        { textContent: 1 },
        { textContent: 8.4, snap: { textContent: 0.1 }, duration: 0.55 },
        "<",
      )
      .to({}, { duration: 0.35 })
      .to([panelUnderstand, titleUnderstand], { autoAlpha: 0, y: -18, duration: 0.35 })
      .to([panelAct, titleAct], { autoAlpha: 1, y: 0, duration: 0.45 }, "<0.1")
      .to(dotUnderstand, { scale: 0.65, opacity: 0.35 }, "<")
      .to(dotAct, { scale: 1.5, opacity: 1 }, "<")
      .to(weights, {
        width: (_index, element) => (element as HTMLElement).dataset["target"] ?? "25%",
        duration: 1,
        ease: "power2.inOut",
      })
      .to(log, { width: "100%", opacity: 1, duration: 0.65 }, "-=0.2")
      .to({}, { duration: 0.4 });
  });

  return (
    <section
      ref={section}
      id="platform"
      data-story-shell
      className="relative isolate overflow-clip bg-paper text-foreground"
    >
      <span id="story" className="absolute left-0 top-0" aria-hidden="true" />
      <div
        ref={stage}
        data-story-stage="paper"
        className="motion-story-stage relative h-svh overflow-hidden"
      >
        <div className="mx-auto grid h-full max-w-[1600px] grid-cols-[0.8fr_1.2fr] items-center gap-14 px-10">
          <div>
            <p className="font-mono text-xs uppercase tracking-label text-primary">
              Signal workflow
            </p>
            <div className="relative mt-8 h-48">
              {["Read.", "Understand.", "Act."].map((title, index) => (
                <div
                  key={title}
                  data-story-title={index}
                  className={`absolute inset-0 ${index ? "invisible opacity-0" : ""}`}
                >
                  <span className="font-mono text-sm tabular-nums text-muted-foreground">
                    0{index + 1} / 03
                  </span>
                  <h2 className="mt-4 font-display text-section leading-none">{title}</h2>
                </div>
              ))}
            </div>
          </div>
          <div className="relative h-[520px]">
            <div data-story-panel="0" className="absolute inset-0">
              <SourceCards />
            </div>
            <div
              data-story-panel="1"
              className="invisible absolute inset-0 flex items-center opacity-0"
            >
              <div className="w-full">
                <p className="mb-10 max-w-xl font-display text-4xl leading-tight">
                  Shipping{" "}
                  <span
                    data-highlight
                    className="bg-[linear-gradient(var(--primary),var(--primary))] bg-[length:0%_100%] bg-no-repeat text-primary-foreground"
                  >
                    restrictions widen
                  </span>{" "}
                  across a{" "}
                  <span
                    data-highlight
                    className="bg-[linear-gradient(var(--primary),var(--primary))] bg-[length:0%_100%] bg-no-repeat text-primary-foreground"
                  >
                    strategic trade corridor
                  </span>
                  .
                </p>
                <Metrics />
              </div>
            </div>
            <div
              data-story-panel="2"
              className="invisible absolute inset-0 flex items-center opacity-0"
            >
              <div className="w-full">
                <Portfolio animated />
              </div>
            </div>
          </div>
        </div>
        <div className="absolute right-7 top-1/2 flex -translate-y-1/2 flex-col gap-4">
          {[0, 1, 2].map((dot) => (
            <span
              key={dot}
              data-story-dot={dot}
              className={`size-1.5 rounded-full bg-primary ${dot ? "scale-[.65] opacity-35" : "scale-150"}`}
            />
          ))}
        </div>
      </div>
      <div className="motion-story-fallback px-5 py-24">
        <p className="font-mono text-xs uppercase tracking-label text-primary">Signal workflow</p>
        <h2 className="mt-5 font-display text-section leading-none">Read. Understand. Act.</h2>
        <div className="mt-14 grid gap-16">
          <section>
            <span className="font-mono text-xs text-muted-foreground">01 / 03</span>
            <h3 className="my-6 font-display text-5xl">Read.</h3>
            <SourceCards compact />
          </section>
          <section>
            <span className="font-mono text-xs text-muted-foreground">02 / 03</span>
            <h3 className="my-6 font-display text-5xl">Understand.</h3>
            <p className="mb-8 font-display text-3xl">
              Shipping restrictions widen across a strategic trade corridor.
            </p>
            <Metrics />
          </section>
          <section>
            <span className="font-mono text-xs text-muted-foreground">03 / 03</span>
            <h3 className="my-6 font-display text-5xl">Act.</h3>
            <Portfolio />
          </section>
        </div>
      </div>
    </section>
  );
}

function PrecedentChart({ animated = false }: { animated?: boolean }) {
  return (
    <div className="relative border-y border-hairline py-6">
      <svg
        viewBox="0 0 620 260"
        className="w-full overflow-visible"
        aria-label="Sample precedent paths and confidence range"
        role="img"
      >
        <path
          data-band={animated ? "" : undefined}
          d="M0 96 C90 70 120 65 175 72 S270 97 320 72 S420 52 470 58 S560 40 620 46 L620 72 C550 66 520 78 460 82 S370 76 310 94 S220 88 165 94 S70 112 0 96Z"
          fill="var(--primary)"
          opacity={animated ? 0 : 0.1}
        />
        <g data-analogs={animated ? "" : undefined} opacity={animated ? 0 : 0.28}>
          {analogs.map((path, index) => (
            <path key={index} d={path} fill="none" stroke="var(--ink)" strokeWidth="1" />
          ))}
        </g>
        <path
          data-current={animated ? "" : undefined}
          d="M0 96 C72 94 105 65 165 72 S252 92 315 63 S397 48 464 55 S548 30 620 38"
          fill="none"
          stroke="var(--primary)"
          strokeWidth="4"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={animated ? 1 : 0}
        />
        <line x1="0" y1="150" x2="620" y2="150" stroke="var(--hairline)" />
        <path
          data-decay={animated ? "" : undefined}
          d="M0 174 C95 177 135 184 205 200 S350 224 620 238"
          fill="none"
          stroke="var(--ink)"
          strokeWidth="2"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={animated ? 1 : 0}
        />
        <g data-half-life={animated ? "" : undefined} opacity={animated ? 0 : 1}>
          <line x1="205" y1="164" x2="205" y2="242" stroke="var(--primary)" strokeDasharray="3 4" />
          <circle cx="205" cy="200" r="4" fill="var(--primary)" />
          <text x="217" y="196" fill="var(--primary)" fontFamily="IBM Plex Mono" fontSize="10">
            HALF-LIFE · 9D
          </text>
        </g>
      </svg>
    </div>
  );
}

export function PrecedentStory() {
  const section = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  useStoryScene(section, 2, ({ gsap, root, priority }) => {
    const scope = stage.current;
    if (!scope) return;
    const notes = gsap.utils.toArray<HTMLElement>("[data-note]", scope);
    const current = scope.querySelector("[data-current]");
    const analogPaths = scope.querySelector("[data-analogs]");
    const band = scope.querySelector("[data-band]");
    const decay = scope.querySelector("[data-decay]");
    const halfLife = scope.querySelector("[data-half-life]");
    const [currentNote, analogNote, bandNote, decayNote] = notes;
    if (
      !currentNote ||
      !analogNote ||
      !bandNote ||
      !decayNote ||
      !current ||
      !analogPaths ||
      !band ||
      !decay ||
      !halfLife
    )
      return;
    gsap.set(notes, { opacity: 0, y: 12 });
    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: root,
        start: "top top",
        end: "+=250%",
        scrub: 0.6,
        pin: scope,
        pinSpacing: true,
        invalidateOnRefresh: true,
        refreshPriority: priority,
      },
    });
    tl.to(current, { strokeDashoffset: 0, duration: 1 })
      .to(currentNote, { opacity: 1, y: 0, duration: 0.3 })
      .to(analogPaths, { opacity: 0.28, duration: 0.8 })
      .to(currentNote, { opacity: 0, duration: 0.2 }, "<")
      .to(analogNote, { opacity: 1, y: 0, duration: 0.3 })
      .to(band, { opacity: 0.1, duration: 0.8 })
      .to(analogNote, { opacity: 0, duration: 0.2 }, "<")
      .to(bandNote, { opacity: 1, y: 0, duration: 0.3 })
      .to(decay, { strokeDashoffset: 0, duration: 0.8 })
      .to(halfLife, { opacity: 1, duration: 0.3 })
      .to(bandNote, { opacity: 0, duration: 0.2 }, "<")
      .to(decayNote, { opacity: 1, y: 0, duration: 0.3 })
      .to({}, { duration: 0.4 });
  });
  const notes = [
    "Current event trajectory",
    "Ten historical analogs",
    "Median confidence range",
    "Influence decays over time",
  ];
  return (
    <section
      ref={section}
      id="precedent"
      data-story-shell
      className="relative isolate overflow-clip bg-surface text-foreground"
    >
      <div
        ref={stage}
        data-story-stage="surface"
        className="motion-story-stage h-svh overflow-hidden"
      >
        <div className="mx-auto grid h-full max-w-[1500px] grid-cols-[0.65fr_1.35fr] items-center gap-16 px-10">
          <div>
            <p className="font-mono text-xs uppercase tracking-label text-primary">
              Historical memory
            </p>
            <h2 className="mt-7 font-display text-section leading-[0.95]">
              Every event has a <em className="text-primary">precedent.</em>
            </h2>
            <div className="relative mt-10 h-10">
              {notes.map((note, index) => (
                <p
                  key={note}
                  data-note={index}
                  className="absolute inset-0 opacity-0 font-mono text-xs uppercase tracking-label text-muted-foreground"
                >
                  {note}
                </p>
              ))}
            </div>
          </div>
          <div>
            <PrecedentChart animated />
            <p className="mt-4 text-right font-mono text-[10px] uppercase tracking-label text-muted-foreground">
              Sample illustration
            </p>
          </div>
        </div>
      </div>
      <div className="motion-story-fallback px-5 py-24">
        <p className="font-mono text-xs uppercase tracking-label text-primary">Historical memory</p>
        <h2 className="mt-5 font-display text-section leading-none">
          Every event has a <em className="text-primary">precedent.</em>
        </h2>
        <div className="mt-14">
          <PrecedentChart />
          <div className="mt-6 grid gap-3">
            {notes.map((note, i) => (
              <p key={note} className="font-mono text-xs text-muted-foreground">
                0{i + 1} — {note}
              </p>
            ))}
          </div>
          <p className="mt-8 font-mono text-[10px] uppercase tracking-label text-muted-foreground">
            Sample illustration
          </p>
        </div>
      </div>
    </section>
  );
}
