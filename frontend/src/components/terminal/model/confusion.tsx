import { rampColor } from "@/lib/severity";
import { formatPct } from "@/lib/format";
import { EmptyState } from "@/components/terminal/kit";
import { MetricsPanel } from "./mpanel";

function valid(labels: string[], matrix: number[][]) {
  return (
    labels.length > 0 &&
    matrix.length === labels.length &&
    matrix.every((r) => Array.isArray(r) && r.length === labels.length)
  );
}

export function ConfusionMatrix() {
  return (
    <MetricsPanel
      title="Event classification confusion matrix"
      info="Rows are the true event type, columns the predicted type. Cell colour is the row-normalised share (recall when on the diagonal)."
      className="lg:col-span-7"
      isEmpty={(m) => !valid(m.event.labels, m.event.confusion)}
      emptyTitle="Confusion matrix unavailable"
    >
      {(m) => {
        const labels = m.event.labels;
        const mat = m.event.confusion;
        if (!valid(labels, mat))
          return (
            <EmptyState
              title="Confusion matrix unavailable"
              hint="Labels and matrix dimensions do not match."
            />
          );
        return (
          <div className="overflow-x-auto" data-lenis-prevent>
            <div
              role="table"
              aria-label="Confusion matrix"
              className="grid min-w-[520px] gap-px text-[10px]"
              style={{ gridTemplateColumns: `110px repeat(${labels.length}, minmax(34px, 1fr))` }}
            >
              <div role="row" className="contents">
                <div className="self-end pb-1 text-right text-muted-foreground">true \ pred</div>
                {labels.map((l) => (
                  <div
                    key={l}
                    role="columnheader"
                    title={l}
                    className="flex h-20 items-end justify-center pb-1 text-muted-foreground"
                  >
                    <span className="max-h-20 truncate [writing-mode:vertical-rl] rotate-180">
                      {l}
                    </span>
                  </div>
                ))}
              </div>
              {mat.map((row, i) => {
                const total = row.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
                return (
                  <div key={labels[i]} role="row" className="contents">
                    <div
                      role="rowheader"
                      title={labels[i]}
                      className="truncate pr-2 text-right leading-[28px] text-muted-foreground"
                    >
                      {labels[i]}
                    </div>
                    {row.map((v, j) => {
                      const pct = total > 0 ? v / total : 0;
                      const diag = i === j;
                      return (
                        <div
                          key={j}
                          role="cell"
                          title={`True ${labels[i]} -> predicted ${labels[j]}: ${v} (${formatPct(pct, 1)} of row)`}
                          className="num flex h-7 items-center justify-center"
                          style={{
                            background:
                              total > 0 ? rampColor(Math.min(0.999, pct)) : "var(--hairline)",
                            opacity: diag || pct > 0 ? 1 : 0.35,
                            outline: diag ? "1.5px solid var(--ink)" : undefined,
                            outlineOffset: -1,
                            color: pct > 0.55 ? "white" : "var(--ink)",
                            fontWeight: diag ? 600 : 400,
                          }}
                        >
                          {v}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        );
      }}
    </MetricsPanel>
  );
}
