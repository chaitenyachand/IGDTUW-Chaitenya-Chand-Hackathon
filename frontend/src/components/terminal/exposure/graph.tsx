import { useEffect, useMemo, useRef, useState } from "react";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore loosely typed: @types may not be installed
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force";

import { flattenSignals, useExposure, usePortfolio, useSignals } from "@/api/client";
import type { Exposure, Signal } from "@/api/types";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { formatCurrency } from "@/lib/format";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const W = 800;
const H = 520;
const HOP_MS = 1200;

interface SimNode {
  id: string;
  label: string;
  type: "counterparty" | "sector";
  notional: number;
  r: number;
  x: number;
  y: number;
  fx: number | null;
  fy: number | null;
}
interface SimLink {
  source: SimNode | string;
  target: SimNode | string;
  weight: number;
}
interface Sim {
  stop(): void;
  on(ev: string, fn: () => void): Sim;
  alpha(a: number): Sim;
  alphaTarget(a: number): Sim;
  restart(): Sim;
  force(name: string, f: unknown): Sim;
}
const d3 = { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } as unknown as {
  forceCenter: (x: number, y: number) => unknown;
  forceCollide: (r: (n: SimNode) => number) => unknown;
  forceLink: (l: SimLink[]) => {
    id: (f: (n: SimNode) => string) => { distance: (d: number) => unknown };
  };
  forceManyBody: () => { strength: (s: number) => unknown };
  forceSimulation: (n: SimNode[]) => Sim;
};

type Graph = Exposure["graph"];

const idOf = (e: SimNode | string) => (typeof e === "string" ? e : e.id);

function scale(v: number, lo: number, hi: number, a: number, b: number) {
  return hi > lo ? a + ((v - lo) / (hi - lo)) * (b - a) : (a + b) / 2;
}

export function ContagionGraph() {
  const exp = useExposure();
  const sig = useSignals({ limit: 100 });
  const pf = usePortfolio();
  const signals = useMemo(() => flattenSignals(sig.data), [sig.data]);
  const [signalId, setSignalId] = useState("none");
  const signal = signals.find((s) => s.id === signalId);

  return (
    <Panel
      title="Contagion graph"
      info="Counterparties (circles) and sectors (squares) sized by notional, linked by exposure weight. Select a signal to see how its impact spreads along the links hop by hop."
      source={exp.data?.meta.source}
      actions={
        <Select value={signalId} onValueChange={setSignalId}>
          <SelectTrigger aria-label="Signal to simulate" className="h-7 w-64 max-w-[60vw] text-xs">
            <SelectValue placeholder="Select a signal" />
          </SelectTrigger>
          <SelectContent data-lenis-prevent>
            <SelectItem value="none">No signal</SelectItem>
            {signals.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {(s.ticker ?? s.entity) + " — " + s.headline.slice(0, 70)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      }
    >
      <QueryBoundary
        query={exp}
        endpoint="GET /api/portfolio/exposure"
        skeleton={<SkeletonBlock className="h-96" />}
        isEmpty={(e) => e.data.graph.nodes.length === 0}
        emptyTitle="No contagion graph"
        emptyHint="The exposure graph has no nodes yet."
      >
        {(env) => (
          <GraphBody graph={env.data.graph} signal={signal} holdings={pf.data?.data ?? []} />
        )}
      </QueryBoundary>
    </Panel>
  );
}

function affectedIds(
  graph: Graph,
  signal: Signal | undefined,
  holdings: { id: string; counterparty: string; sector: string }[],
) {
  const out = new Set<string>();
  if (!signal) return out;
  const names = new Set<string>();
  for (const s of [signal.entity, signal.ticker]) if (s) names.add(s.toLowerCase());
  const byId = new Map(holdings.map((h) => [h.id, h]));
  for (const a of signal.affectedHoldings) {
    const h = byId.get(a.holdingId);
    if (h) {
      names.add(h.counterparty.toLowerCase());
      names.add(h.sector.toLowerCase());
    }
  }
  for (const n of graph.nodes) if (names.has(n.label.toLowerCase())) out.add(n.id);
  return out;
}

/** Multi-source BFS over undirected edges. */
function hops(graph: Graph, sources: Set<string>) {
  const adj = new Map<string, string[]>();
  for (const e of graph.edges) {
    (adj.get(e.source) ?? adj.set(e.source, []).get(e.source))?.push(e.target);
    (adj.get(e.target) ?? adj.set(e.target, []).get(e.target))?.push(e.source);
  }
  const dist = new Map<string, number>();
  let frontier = [...sources];
  frontier.forEach((s) => dist.set(s, 0));
  let d = 0;
  while (frontier.length) {
    d++;
    const next: string[] = [];
    for (const id of frontier)
      for (const nb of adj.get(id) ?? [])
        if (!dist.has(nb)) {
          dist.set(nb, d);
          next.push(nb);
        }
    frontier = next;
  }
  return dist;
}

function GraphBody({
  graph,
  signal,
  holdings,
}: {
  graph: Graph;
  signal: Signal | undefined;
  holdings: { id: string; counterparty: string; sector: string }[];
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<Sim | null>(null);
  const raf = useRef(0);
  const [, setTick] = useState(0);
  const [hoverId, setHoverId] = useState<string | null>(null);

  const { nodes, links, maxW, minW } = useMemo(() => {
    const ns = graph.nodes.map((n) => n.notional);
    const lo = Math.sqrt(Math.max(0, Math.min(...ns)));
    const hi = Math.sqrt(Math.max(0, Math.max(...ns)));
    const ids = new Set(graph.nodes.map((n) => n.id));
    const nodes: SimNode[] = graph.nodes.map((n, i) => ({
      ...n,
      r: scale(Math.sqrt(Math.max(0, n.notional)), lo, hi, 5, 22),
      x: W / 2 + Math.cos(i) * 120,
      y: H / 2 + Math.sin(i) * 120,
      fx: null,
      fy: null,
    }));
    const links: SimLink[] = graph.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({ ...e }));
    const ws = links.map((l) => l.weight);
    return {
      nodes,
      links,
      minW: ws.length ? Math.min(...ws) : 0,
      maxW: ws.length ? Math.max(...ws) : 0,
    };
  }, [graph]);

  useEffect(() => {
    const sim = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((n) => n.id)
          .distance(70),
      )
      .force("charge", d3.forceManyBody().strength(-160))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force(
        "collide",
        d3.forceCollide((n) => n.r + 3),
      );
    sim.on("tick", () => {
      if (raf.current) return;
      raf.current = requestAnimationFrame(() => {
        raf.current = 0;
        for (const n of nodes) {
          n.x = Math.min(W - n.r, Math.max(n.r, n.x));
          n.y = Math.min(H - n.r, Math.max(n.r, n.y));
        }
        setTick((t) => t + 1);
      });
    });
    simRef.current = sim;
    return () => {
      sim.stop();
      if (raf.current) cancelAnimationFrame(raf.current);
      raf.current = 0;
    };
  }, [nodes, links]);

  /* ripple */
  const affected = useMemo(() => affectedIds(graph, signal, holdings), [graph, signal, holdings]);
  const dist = useMemo(() => hops(graph, affected), [graph, affected]);
  const maxHop = useMemo(() => Math.max(0, ...dist.values()), [dist]);
  const [wave, setWave] = useState(-1);
  useEffect(() => {
    if (affected.size === 0) {
      setWave(-1);
      return;
    }
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setWave(maxHop);
      return;
    }
    setWave(0);
    let h = 0;
    const iv = window.setInterval(() => {
      h++;
      setWave(h);
      if (h >= maxHop) window.clearInterval(iv);
    }, HOP_MS);
    return () => window.clearInterval(iv);
  }, [affected, maxHop]);

  const reached = (id: string) => wave >= 0 && (dist.get(id) ?? Infinity) <= wave;

  /* drag */
  const drag = useRef<SimNode | null>(null);
  const toSvg = (e: React.PointerEvent) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r || r.width === 0) return { x: 0, y: 0 };
    return { x: ((e.clientX - r.left) / r.width) * W, y: ((e.clientY - r.top) / r.height) * H };
  };
  const onDown = (n: SimNode) => (e: React.PointerEvent) => {
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    drag.current = n;
    const p = toSvg(e);
    n.fx = p.x;
    n.fy = p.y;
    simRef.current?.alphaTarget(0.3).restart();
  };
  const onMove = (e: React.PointerEvent) => {
    const n = drag.current;
    if (!n) return;
    const p = toSvg(e);
    n.fx = p.x;
    n.fy = p.y;
  };
  const onUp = () => {
    const n = drag.current;
    if (n) {
      n.fx = null;
      n.fy = null;
    }
    drag.current = null;
    simRef.current?.alphaTarget(0);
  };

  const hover = hoverId ? nodes.find((n) => n.id === hoverId) : undefined;
  const pos = (e: SimNode | string) => (typeof e === "string" ? undefined : e);

  return (
    <div>
      <div
        className="mb-1 flex min-h-5 flex-wrap items-center justify-between gap-2 text-[11px]"
        aria-live="polite"
      >
        {hover ? (
          <span>
            <span className="font-medium">{hover.label}</span>{" "}
            <span className="num text-muted-foreground">
              {hover.type} · {formatCurrency(hover.notional)}
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground">
            Drag nodes to rearrange. Hover for notional.
          </span>
        )}
        {signal ? (
          <span className="text-muted-foreground">
            {affected.size > 0
              ? `${affected.size} directly affected node${affected.size === 1 ? "" : "s"}; spreading ${maxHop} hop${maxHop === 1 ? "" : "s"}`
              : "This signal matches no node in the graph"}
          </span>
        ) : null}
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full touch-none rounded-sm border border-hairline"
        role="img"
        aria-label="Counterparty and sector contagion graph"
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
      >
        {links.map((l, i) => {
          const a = pos(l.source);
          const b = pos(l.target);
          if (!a || !b) return null;
          const hit = reached(a.id) && reached(b.id);
          return (
            <line
              key={`${idOf(l.source)}-${idOf(l.target)}-${i}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={hit ? "var(--primary)" : "var(--hairline)"}
              strokeOpacity={hit ? 0.9 : 1}
              strokeWidth={scale(l.weight, minW, maxW, 0.75, 4)}
            />
          );
        })}
        {nodes.map((n) => {
          const hit = reached(n.id);
          const fill = hit
            ? "var(--primary)"
            : n.type === "sector"
              ? "var(--paper)"
              : "oklch(0.72 0.006 285)";
          return (
            <g
              key={n.id}
              transform={`translate(${n.x},${n.y})`}
              className="cursor-grab active:cursor-grabbing"
              onPointerDown={onDown(n)}
              onPointerEnter={() => setHoverId(n.id)}
              onPointerLeave={() => setHoverId(null)}
            >
              {hit && (dist.get(n.id) ?? -1) === wave ? (
                <circle r={n.r + 4} fill="var(--primary)" opacity={0.3} className="pin-pulse" />
              ) : null}
              {n.type === "sector" ? (
                <rect
                  x={-n.r}
                  y={-n.r}
                  width={n.r * 2}
                  height={n.r * 2}
                  fill={fill}
                  stroke="var(--primary)"
                  strokeWidth={1.5}
                />
              ) : (
                <circle r={n.r} fill={fill} stroke="var(--ink)" strokeWidth={1} />
              )}
              {n.r > 11 || hit || hoverId === n.id ? (
                <text
                  y={n.r + 11}
                  textAnchor="middle"
                  fontSize={10}
                  fill="var(--ink)"
                  className="pointer-events-none select-none"
                >
                  {n.label}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-full border border-[var(--ink)] bg-[oklch(0.72_0.006_285)]" />{" "}
          Counterparty
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 border border-primary bg-paper" /> Sector
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-primary" /> Affected link
        </span>
        <span>Node size ~ √notional; link width ~ weight</span>
      </div>
    </div>
  );
}
