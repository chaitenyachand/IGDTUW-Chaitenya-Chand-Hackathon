import { useRef, type ReactNode } from "react";

import { useStoryScene } from "./story-motion";

import { cn } from "@/lib/utils";

type Signal = {
  entity: string;
  ticker: string;
  type: string;
  sentiment: number;
  impact: 1 | 2 | 3 | 4 | 5;
  time: string;
};

// Sample data only — illustrative, not real market events.
const SIGNALS: Signal[] = [
  {
    entity: "Meridian Shipping",
    ticker: "MRDN",
    type: "Sanctions",
    sentiment: -0.72,
    impact: 5,
    time: "09:41:12",
  },
  {
    entity: "Kestrel Semiconductors",
    ticker: "KSTL",
    type: "Supply chain",
    sentiment: -0.48,
    impact: 4,
    time: "09:39:58",
  },
  {
    entity: "Arden Energy",
    ticker: "ARDN",
    type: "Regulatory",
    sentiment: -0.31,
    impact: 3,
    time: "09:37:20",
  },
  {
    entity: "Halvorsen Bank",
    ticker: "HLVB",
    type: "Credit",
    sentiment: -0.58,
    impact: 4,
    time: "09:35:07",
  },
  {
    entity: "Corvid Pharma",
    ticker: "CRVD",
    type: "Litigation",
    sentiment: -0.22,
    impact: 2,
    time: "09:33:44",
  },
  {
    entity: "Talon Aerospace",
    ticker: "TALN",
    type: "Geopolitical",
    sentiment: -0.64,
    impact: 5,
    time: "09:31:16",
  },
  {
    entity: "Brightwater Utilities",
    ticker: "BWTR",
    type: "Weather",
    sentiment: -0.15,
    impact: 1,
    time: "09:29:03",
  },
  {
    entity: "Novacrest Retail",
    ticker: "NVCR",
    type: "Earnings",
    sentiment: 0.34,
    impact: 2,
    time: "09:26:51",
  },
  {
    entity: "Orison Metals",
    ticker: "ORSN",
    type: "Labor",
    sentiment: -0.41,
    impact: 3,
    time: "09:24:30",
  },
];

const severityBg = [
  "",
  "bg-severity-1",
  "bg-severity-2",
  "bg-severity-3",
  "bg-severity-4",
  "bg-severity-5",
];
const severityFg = [
  "",
  "text-foreground",
  "text-foreground",
  "text-primary-foreground",
  "text-primary-foreground",
  "text-primary-foreground",
];

function SignalRow({ s }: { s: Signal }) {
  const pct = Math.abs(s.sentiment) * 50;
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-hairline px-5 py-3.5 sm:grid-cols-[1.6fr_1fr_1.2fr_auto]">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{s.entity}</div>
        <div className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {s.ticker} · {s.time}
        </div>
      </div>
      <span className="hidden w-fit rounded-sm border border-hairline px-2 py-0.5 font-mono text-[10px] uppercase tracking-label text-secondary-foreground sm:inline-block">
        {s.type}
      </span>
      <div className="hidden items-center gap-2 sm:flex">
        <div className="relative h-1.5 flex-1 bg-surface">
          <div className="absolute inset-y-0 left-1/2 w-px bg-hairline" />
          <div
            className={cn("absolute inset-y-0", s.sentiment < 0 ? "bg-primary" : "bg-positive")}
            style={
              s.sentiment < 0
                ? { right: "50%", width: `${pct}%` }
                : { left: "50%", width: `${pct}%` }
            }
          />
        </div>
        <span className="w-10 text-right font-mono text-[11px] tabular-nums">
          {s.sentiment.toFixed(2)}
        </span>
      </div>
      <span
        className={cn(
          "rounded-sm px-2 py-0.5 font-mono text-[11px] tabular-nums",
          severityBg[s.impact],
          severityFg[s.impact],
        )}
      >
        S{s.impact}
      </span>
    </div>
  );
}

/** Default preview contents. Replace via <ProductPreview media={...}> (e.g. a looping <video>). */
export function SampleSignalFeed() {
  return (
    <div className="relative h-full overflow-hidden">
      <div className="animate-signal-scroll">
        {[...SIGNALS, ...SIGNALS].map((s, i) => (
          <SignalRow key={i} s={s} />
        ))}
      </div>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-paper to-transparent" />
    </div>
  );
}

export function ProductPreview({ media }: { media?: ReactNode }) {
  const wrap = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLDivElement>(null);

  useStoryScene(
    wrap,
    0,
    ({ gsap, root, priority }) => {
      gsap.fromTo(
        frame.current,
        { scale: 0.92, y: 80, rotateX: 14 },
        {
          scale: 1,
          y: 0,
          rotateX: 2,
          ease: "none",
          scrollTrigger: {
            trigger: root,
            start: "top bottom",
            end: "top 20%",
            scrub: true,
            refreshPriority: priority,
          },
        },
      );
    },
    "(prefers-reduced-motion: no-preference)",
  );

  return (
    <div ref={wrap} className="mx-auto max-w-[1200px] px-5 [perspective:1600px] lg:px-10">
      <div
        ref={frame}
        className="origin-top overflow-hidden rounded-xl border border-hairline bg-paper shadow-[0_40px_120px_-40px_color-mix(in_oklab,var(--ink)_35%,transparent)] will-change-transform"
      >
        <div className="flex items-center justify-between border-b border-hairline bg-surface px-4 py-3">
          <div className="flex gap-1.5">
            <span className="size-2.5 rounded-full bg-hairline" />
            <span className="size-2.5 rounded-full bg-hairline" />
            <span className="size-2.5 rounded-full bg-hairline" />
          </div>
          <span className="font-mono text-[10px] uppercase tracking-label text-muted-foreground">
            Live signals
          </span>
          <span className="rounded-sm border border-hairline px-2 py-0.5 font-mono text-[10px] uppercase tracking-label text-muted-foreground">
            Sample data
          </span>
        </div>
        {/* PREVIEW MEDIA SLOT — pass `media` (e.g. a looping screen-recording <video>) to replace the sample feed. */}
        <div data-slot="preview-media" className="h-[420px] sm:h-[520px]">
          {media ?? <SampleSignalFeed />}
        </div>
      </div>
    </div>
  );
}
