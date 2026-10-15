import { useEffect, useMemo, useRef, useState } from "react";

import { useExposure } from "@/api/client";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { formatCurrency, formatPct } from "@/lib/format";
import { rampColor } from "@/lib/severity";
import { squarify } from "./squarify";

type Row = { sector: string; exposure: number; stressedLoss: number };
const H = 380;

export function SectorTreemap() {
  const q = useExposure();
  return (
    <Panel
      title="Sector treemap"
      info="Tile area is sector exposure. Colour is stressed loss as a share of that sector's exposure, scaled to the worst sector."
      source={q.data?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/portfolio/exposure"
        skeleton={<SkeletonBlock className="h-96" />}
        isEmpty={(e) => e.data.bySector.filter((s) => s.exposure > 0).length === 0}
        emptyTitle="No sector exposure"
      >
        {(env) => <Tree rows={env.data.bySector.filter((s) => s.exposure > 0)} />}
      </QueryBoundary>
    </Panel>
  );
}

function Tree({ rows }: { rows: Row[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [hover, setHover] = useState<Row | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth);
    const ro = new ResizeObserver((es) => setW(es[0]?.contentRect.width ?? el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const sorted = useMemo(() => [...rows].sort((a, b) => b.exposure - a.exposure), [rows]);
  const rects = useMemo(
    () =>
      squarify(
        sorted.map((r) => r.exposure),
        w,
        H,
      ),
    [sorted, w],
  );
  const maxRatio = Math.max(0, ...sorted.map((r) => r.stressedLoss / r.exposure));

  return (
    <div>
      <div className="mb-1 min-h-5 text-[11px]" aria-live="polite">
        {hover ? (
          <span>
            <span className="font-medium">{hover.sector}</span>{" "}
            <span className="num text-muted-foreground">
              {formatCurrency(hover.exposure)} exposure · {formatCurrency(hover.stressedLoss)}{" "}
              stressed loss ({formatPct(hover.stressedLoss / hover.exposure, 1)})
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground">Hover or focus a tile for details.</span>
        )}
      </div>
      <div
        ref={ref}
        className="relative w-full overflow-hidden rounded-sm border border-hairline"
        style={{ height: H }}
      >
        {rects.map((r, i) => {
          const row = sorted[i];
          if (!row) return null;
          const ratio = row.stressedLoss / row.exposure;
          const t = maxRatio > 0 ? ratio / maxRatio : 0;
          const dark = t >= 0.4;
          const roomy = r.w > 70 && r.h > 34;
          return (
            <button
              key={row.sector}
              type="button"
              aria-label={`${row.sector}: ${formatCurrency(row.exposure)} exposure, ${formatCurrency(row.stressedLoss)} stressed loss`}
              onMouseEnter={() => setHover(row)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(row)}
              onBlur={() => setHover(null)}
              className="absolute overflow-hidden border border-paper p-1.5 text-left outline-none focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-ring"
              style={{
                left: r.x,
                top: r.y,
                width: Math.max(0, r.w),
                height: Math.max(0, r.h),
                background: rampColor(t),
                color: dark ? "white" : "var(--ink)",
              }}
            >
              {roomy ? (
                <>
                  <div className="truncate text-xs font-medium">{row.sector}</div>
                  <div className="num text-[11px] opacity-90">{formatCurrency(row.exposure)}</div>
                </>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
