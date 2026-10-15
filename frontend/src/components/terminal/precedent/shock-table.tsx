import { AlertTriangle, ArrowRight } from "lucide-react";

import type { PrecedentResult, ProvenanceSource } from "@/api/types";
import { formatDate, formatPct } from "@/lib/format";
import { ASSET_LABEL } from "@/lib/precedent";
import { EmptyState, Panel } from "@/components/terminal/kit";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ShockTable({
  precedent,
  source,
  onRun,
}: {
  precedent: PrecedentResult;
  source: ProvenanceSource;
  onRun: () => void;
}) {
  return (
    <Panel
      title="Calibrated shock vector"
      info="Per asset class: the median move, and the 10th to 90th percentile range, observed across the historical analogs. n is the number of analogs behind each estimate."
      source={source}
      actions={
        <button
          type="button"
          onClick={onRun}
          className="inline-flex items-center gap-1.5 rounded-sm bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground outline-none transition-opacity hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
        >
          Run in Stress Lab <ArrowRight className="size-3.5" />
        </button>
      }
    >
      {precedent.shocks.length === 0 ? (
        <EmptyState title="No calibrated shocks for this signal" className="py-6" />
      ) : (
        <div data-lenis-prevent className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-[12px]">
            <thead className="text-[10px] uppercase tracking-label text-muted-foreground">
              <tr className="border-b border-hairline">
                <th className="py-1.5 text-left font-medium">Asset class</th>
                <th className="py-1.5 text-right font-medium">Median shock</th>
                <th className="py-1.5 text-right font-medium">P10 – P90</th>
                <th className="py-1.5 text-right font-medium">n</th>
              </tr>
            </thead>
            <tbody>
              {precedent.shocks.map((s) => (
                <tr key={s.assetClass} className="border-b border-hairline/60">
                  <td className="py-1.5">{ASSET_LABEL[s.assetClass]}</td>
                  <td className="num py-1.5 text-right">{formatPct(s.median, 2, true)}</td>
                  <td className="num py-1.5 text-right text-muted-foreground">
                    {formatPct(s.p10, 2, true)} to {formatPct(s.p90, 2, true)}
                  </td>
                  <td className="py-1.5 text-right">
                    <span className="inline-flex items-center justify-end gap-1.5">
                      <span className="num">{s.n}</span>
                      {s.n < 10 ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span
                              tabIndex={0}
                              className="inline-flex items-center gap-1 rounded-sm border border-primary/50 bg-accent px-1 text-[10px] leading-4 text-primary outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            >
                              <AlertTriangle className="size-3" /> Low n
                            </span>
                          </TooltipTrigger>
                          <TooltipContent className="text-xs">
                            Small sample (n &lt; 10): treat this estimate with caution.
                          </TooltipContent>
                        </Tooltip>
                      ) : null}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="num mt-2 text-[11px] text-muted-foreground">
        n = {precedent.n} analogs · History used: {formatDate(precedent.dateRange.from)} –{" "}
        {formatDate(precedent.dateRange.to)}
      </p>
    </Panel>
  );
}
