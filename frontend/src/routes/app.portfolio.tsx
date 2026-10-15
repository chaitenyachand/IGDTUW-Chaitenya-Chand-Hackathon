import { createFileRoute } from "@tanstack/react-router";

import { usePortfolio } from "@/api/client";
import { ProvenanceBadge } from "@/components/terminal/kit";
import { ImportCsv } from "@/components/terminal/portfolio/import-dialog";
import { PortfolioView } from "@/components/terminal/portfolio/holdings";

export const Route = createFileRoute("/app/portfolio")({
  head: () => ({ meta: [{ title: "Portfolio — SENTINEL Terminal" }] }),
  component: Portfolio,
});

function Portfolio() {
  const q = usePortfolio();
  const source = q.data?.meta.source;
  return (
    <div className="space-y-3 p-4 text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-muted-foreground">
          Synthetic portfolio built from sample transaction data.
        </p>
        {source ? <ProvenanceBadge source={source} /> : null}
      </div>
      <PortfolioView action={<ImportCsv />} />
    </div>
  );
}
