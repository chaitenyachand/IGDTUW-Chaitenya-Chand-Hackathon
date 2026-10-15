import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";

import { useConstituents } from "@/api/client";
import type { IndexConstituent } from "@/api/types";
import { IntegrityDot, SentimentBar } from "@/components/terminal/chips";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { formatPct } from "@/lib/format";
import { compareNullable } from "@/lib/severity";

type Key = "ticker" | "benchmarkWeight" | "currentWeight" | "delta" | "sentiment" | "integrity";
const delta = (c: IndexConstituent) => c.currentWeight - c.benchmarkWeight;

function DeltaBar({ d, max }: { d: number; max: number }) {
  const w = max > 0 ? Math.min(50, (Math.abs(d) / max) * 50) : 0;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative h-1.5 w-20 rounded-full bg-surface" aria-hidden>
        <span className="absolute inset-y-[-2px] left-1/2 w-px bg-hairline" />
        <span
          className="absolute inset-y-0"
          style={{
            left: d < 0 ? `${50 - w}%` : "50%",
            width: `${w}%`,
            background: d < 0 ? "var(--primary)" : "var(--positive)",
          }}
        />
      </span>
      <span className="num w-14 text-right text-[11px] text-foreground">
        {formatPct(d, 2, true)}
      </span>
    </span>
  );
}

function Inner({ rows }: { rows: IndexConstituent[] }) {
  const [key, setKey] = useState<Key>("currentWeight");
  const [dir, setDir] = useState<"asc" | "desc">("desc");
  const sorted = useMemo(() => {
    const val = (c: IndexConstituent): number | string | null =>
      key === "delta" ? delta(c) : c[key];
    return [...rows].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      if (typeof x === "string" || typeof y === "string")
        return dir === "asc"
          ? String(x).localeCompare(String(y))
          : String(y).localeCompare(String(x));
      return compareNullable(x, y, dir);
    });
  }, [rows, key, dir]);
  const maxD = useMemo(() => Math.max(0, ...rows.map((c) => Math.abs(delta(c)))), [rows]);

  const Th = ({ k, label, right }: { k: Key; label: string; right?: boolean }) => (
    <th
      scope="col"
      aria-sort={key === k ? (dir === "asc" ? "ascending" : "descending") : "none"}
      className={`py-1 font-medium ${right ? "text-right" : "text-left"}`}
    >
      <button
        type="button"
        onClick={() => {
          if (k === key) setDir(dir === "asc" ? "desc" : "asc");
          else {
            setKey(k);
            setDir(k === "ticker" ? "asc" : "desc");
          }
        }}
        className="inline-flex items-center gap-0.5 uppercase tracking-label outline-none hover:text-foreground focus-visible:text-foreground"
      >
        {label}
        {key === k ? (
          dir === "asc" ? (
            <ArrowUp className="size-3" />
          ) : (
            <ArrowDown className="size-3" />
          )
        ) : null}
      </button>
    </th>
  );

  return (
    <div data-lenis-prevent className="max-h-[420px] overflow-auto">
      <table className="w-full min-w-[560px] text-[12px]">
        <thead className="sticky top-0 bg-paper text-[11px] text-muted-foreground">
          <tr className="border-b border-hairline">
            <Th k="ticker" label="Constituent" />
            <Th k="benchmarkWeight" label="Bench" right />
            <Th k="currentWeight" label="Current" right />
            <Th k="delta" label="Delta" />
            <Th k="sentiment" label="Sentiment" />
            <Th k="integrity" label="Integrity" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => (
            <tr
              key={c.ticker}
              className="border-b border-hairline last:border-b-0 hover:bg-surface"
            >
              <td className="py-1.5 pr-2">
                <div className="flex items-baseline gap-1.5">
                  <span className="num text-[12px] font-medium text-foreground">{c.ticker}</span>
                  <span className="truncate text-muted-foreground">{c.name}</span>
                </div>
                <div className="text-[11px] text-muted-foreground">{c.sector}</div>
              </td>
              <td className="num py-1.5 text-right text-muted-foreground">
                {formatPct(c.benchmarkWeight, 2)}
              </td>
              <td className="num py-1.5 text-right text-foreground">
                {formatPct(c.currentWeight, 2)}
              </td>
              <td className="py-1.5 pl-3">
                <DeltaBar d={delta(c)} max={maxD} />
              </td>
              <td className="py-1.5">
                <SentimentBar value={c.sentiment} />
              </td>
              <td className="py-1.5">
                <IntegrityDot score={c.integrity} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ConstituentsPanel() {
  const q = useConstituents();
  return (
    <Panel
      title="Constituents"
      info="Benchmark weight, current sentiment-tilted weight and their difference (delta) per constituent, with the latest sentiment (-1..1) and integrity score (0..1)."
      source={q.data?.meta.source}
      bodyClassName="p-0 px-3 pb-2"
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/index/constituents"
        skeleton={<SkeletonBlock lines={8} className="pt-3" />}
        isEmpty={(e) => e.data.length === 0}
        emptyTitle="No constituents"
      >
        {(env) => <Inner rows={env.data} />}
      </QueryBoundary>
    </Panel>
  );
}
