import { Check, X } from "lucide-react";

import { useRebalanceDecision, useRebalances } from "@/api/client";
import type { RebalanceEvent } from "@/api/types";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { formatPct } from "@/lib/format";
import { openSignal } from "@/lib/drawer";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";
import { fmtStamp } from "./util";

const STATUS: Record<RebalanceEvent["status"], string> = {
  applied: "border-[var(--positive)] text-[var(--positive)]",
  pending: "border-primary text-primary",
  rejected: "border-hairline text-muted-foreground",
};

function Item({ r, tz }: { r: RebalanceEvent; tz: "UTC" | "local" }) {
  const dec = useRebalanceDecision();
  const top = [...r.moves]
    .sort((a, b) => Math.abs(b.to - b.from) - Math.abs(a.to - a.from))
    .slice(0, 3);
  const act = (decision: "approve" | "reject") => dec.mutate({ id: r.id, decision });
  const b =
    "inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-[11px] font-medium outline-none transition-colors focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50";
  return (
    <li className="relative border-l border-hairline pb-3 pl-4 last:pb-0">
      <span
        className={cn(
          "absolute -left-[4.5px] top-1 size-2 rounded-full",
          r.status === "pending"
            ? "bg-primary"
            : r.status === "applied"
              ? "bg-[var(--positive)]"
              : "bg-hairline",
        )}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="num text-[11px] text-muted-foreground">{fmtStamp(r.ts, tz)}</span>
        <span
          className={cn(
            "rounded-sm border px-1.5 text-[10px] uppercase leading-4 tracking-wider",
            STATUS[r.status],
          )}
        >
          {r.status}
        </span>
      </div>
      <button
        type="button"
        onClick={() => openSignal(r.triggerSignalId)}
        className="mt-0.5 text-left text-[12px] font-medium text-foreground underline-offset-2 outline-none hover:text-primary hover:underline focus-visible:underline"
      >
        {r.triggerHeadline}
      </button>
      <ul className="mt-1 space-y-0.5">
        {top.map((m) => (
          <li key={m.ticker} className="num text-[11px] text-muted-foreground">
            <span className="text-foreground">{m.ticker}</span> {formatPct(m.from, 1)} →{" "}
            {formatPct(m.to, 1)}
          </li>
        ))}
        {top.length === 0 ? (
          <li className="text-[11px] text-muted-foreground">No moves recorded</li>
        ) : null}
      </ul>
      {r.status === "pending" ? (
        <div className="mt-1.5 flex gap-1.5">
          <button
            type="button"
            disabled={dec.isPending}
            onClick={() => act("approve")}
            className={cn(b, "border-primary bg-primary text-primary-foreground hover:opacity-90")}
          >
            <Check className="size-3" /> Approve
          </button>
          <button
            type="button"
            disabled={dec.isPending}
            onClick={() => act("reject")}
            className={cn(
              b,
              "border-hairline bg-paper text-foreground hover:border-primary hover:text-primary",
            )}
          >
            <X className="size-3" /> Reject
          </button>
        </div>
      ) : null}
    </li>
  );
}

export function RebalanceLog() {
  const q = useRebalances();
  const { tz } = useSettings();
  return (
    <Panel
      title="Rebalance log"
      info="Rebalance events, newest first, with the trigger signal, the three largest weight moves and status. Pending items need PM approval."
      source={q.data?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/index/rebalances"
        skeleton={<SkeletonBlock lines={6} />}
        isEmpty={(e) => e.data.length === 0}
        emptyTitle="No rebalances yet"
        emptyHint="Rebalances appear when a high-integrity signal moves a constituent past the sentiment threshold."
      >
        {(env) => (
          <ol data-lenis-prevent className="ml-1 max-h-[420px] overflow-y-auto pr-1">
            {[...env.data]
              .sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts))
              .map((r) => (
                <Item key={r.id} r={r} tz={tz} />
              ))}
          </ol>
        )}
      </QueryBoundary>
    </Panel>
  );
}
