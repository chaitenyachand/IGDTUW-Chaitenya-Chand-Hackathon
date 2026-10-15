import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";

import { useHealth } from "@/api/client";
import type { HealthSource } from "@/api/types";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { cn } from "@/lib/utils";
import { formatNumber, formatRelativeTime } from "@/lib/format";
import { compareNullable } from "@/lib/severity";

type Key =
  "name" | "status" | "lastSuccess" | "lastError" | "itemsLastRun" | "itemsTotal" | "errorCount";
const COLS: { key: Key; label: string; num?: boolean }[] = [
  { key: "name", label: "Source" },
  { key: "status", label: "Status" },
  { key: "lastSuccess", label: "Last success" },
  { key: "lastError", label: "Last error" },
  { key: "itemsLastRun", label: "Items (last run)", num: true },
  { key: "itemsTotal", label: "Items (total)", num: true },
  { key: "errorCount", label: "Errors", num: true },
];

const CHIP: Record<HealthSource["status"], string> = {
  ok: "border-[var(--positive)] text-[var(--positive)]",
  error: "border-primary bg-primary/10 text-primary",
  disabled: "border-hairline text-muted-foreground",
  starting: "border-[var(--severity-3)] text-foreground",
};

function sortValue(s: HealthSource, k: Key): number | string | null {
  if (k === "lastSuccess") return s.lastSuccess ? Date.parse(s.lastSuccess) : null;
  if (k === "lastError") return s.lastError;
  return s[k];
}

export function SourceHealthTable() {
  const q = useHealth();
  const [key, setKey] = useState<Key>("status");
  const [dir, setDir] = useState<"asc" | "desc">("asc");
  const sources = q.data?.data.sources;
  const rows = useMemo(() => {
    const list = [...(sources ?? [])];
    list.sort((a, b) => {
      const av = sortValue(a, key);
      const bv = sortValue(b, key);
      if (typeof av === "string" || typeof bv === "string") {
        if (av == null || bv == null)
          return compareNullable(av == null ? null : 0, bv == null ? null : 0, dir);
        return dir === "asc"
          ? String(av).localeCompare(String(bv))
          : String(bv).localeCompare(String(av));
      }
      return compareNullable(av, bv, dir);
    });
    return list;
  }, [sources, key, dir]);

  const toggle = (k: Key) => {
    if (k === key) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setKey(k);
      setDir(k === "name" || k === "status" ? "asc" : "desc");
    }
  };

  return (
    <Panel
      title="Source health"
      info="Per-source ingestion status from the pipeline. Rows with errors are highlighted; click a header to sort."
      source={q.data?.meta.source}
      className="lg:col-span-12"
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/health"
        skeleton={<SkeletonBlock lines={5} />}
        isEmpty={(e) => e.data.sources.length === 0}
        emptyTitle="No sources reported"
      >
        {() => (
          <div className="overflow-x-auto" data-lenis-prevent>
            <table className="w-full min-w-[760px] text-left text-[12px]">
              <thead>
                <tr className="border-b border-hairline text-[10px] uppercase tracking-label text-muted-foreground">
                  {COLS.map((c) => (
                    <th
                      key={c.key}
                      scope="col"
                      aria-sort={
                        key === c.key ? (dir === "asc" ? "ascending" : "descending") : "none"
                      }
                      className={cn("px-2 py-1.5 font-medium", c.num && "text-right")}
                    >
                      <button
                        type="button"
                        onClick={() => toggle(c.key)}
                        className="inline-flex items-center gap-1 uppercase outline-none hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {c.label}
                        {key === c.key ? (
                          dir === "asc" ? (
                            <ArrowUp className="size-3" />
                          ) : (
                            <ArrowDown className="size-3" />
                          )
                        ) : null}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr
                    key={s.name}
                    className={cn(
                      "border-b border-hairline last:border-0",
                      s.status === "error" && "bg-primary/5",
                    )}
                  >
                    <td className="px-2 py-1.5 font-medium">{s.name}</td>
                    <td className="px-2 py-1.5">
                      <span
                        className={cn(
                          "rounded-sm border px-1.5 py-0.5 text-[10px] uppercase tracking-wider",
                          CHIP[s.status] ?? CHIP.disabled,
                        )}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="num px-2 py-1.5">{formatRelativeTime(s.lastSuccess)}</td>
                    <td
                      className={cn(
                        "max-w-[280px] truncate px-2 py-1.5",
                        s.lastError && "text-primary",
                      )}
                      title={s.lastError ?? undefined}
                    >
                      {s.lastError ?? "—"}
                    </td>
                    <td className="num px-2 py-1.5 text-right">
                      {formatNumber(s.itemsLastRun, { maximumFractionDigits: 0 })}
                    </td>
                    <td className="num px-2 py-1.5 text-right">
                      {formatNumber(s.itemsTotal, { maximumFractionDigits: 0 })}
                    </td>
                    <td
                      className={cn(
                        "num px-2 py-1.5 text-right",
                        s.errorCount > 0 && "text-primary",
                      )}
                    >
                      {formatNumber(s.errorCount, { maximumFractionDigits: 0 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryBoundary>
    </Panel>
  );
}
