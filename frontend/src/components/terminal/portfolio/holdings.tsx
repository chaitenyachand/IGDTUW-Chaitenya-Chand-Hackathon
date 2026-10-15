import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Search } from "lucide-react";

import { usePortfolio } from "@/api/client";
import type { Holding, ProvenanceSource } from "@/api/types";
import { EmptyState, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatCurrency, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AssetDonut } from "./donut";

type Key =
  | "assetType"
  | "counterparty"
  | "sector"
  | "country"
  | "notional"
  | "marketValue"
  | "rating"
  | "maturity";
const COLS: { k: Key; label: string; right?: boolean }[] = [
  { k: "assetType", label: "Asset type" },
  { k: "counterparty", label: "Counterparty" },
  { k: "sector", label: "Sector" },
  { k: "country", label: "Country" },
  { k: "notional", label: "Notional", right: true },
  { k: "marketValue", label: "Market value", right: true },
  { k: "rating", label: "Rating" },
  { k: "maturity", label: "Maturity" },
];
const ALL = "__all__";
const uniq = (xs: string[]) => [...new Set(xs)].sort((a, b) => a.localeCompare(b));

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={label} className="h-7 w-36 rounded-sm text-xs">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All {label.toLowerCase()}s</SelectItem>
        {options.map((o) => (
          <SelectItem key={o} value={o}>
            {o}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function View({
  rows,
  action,
  source,
}: {
  rows: Holding[];
  action: React.ReactNode;
  source: ProvenanceSource | undefined;
}) {
  const [types, setTypes] = useState<string[]>([]);
  const [sector, setSector] = useState(ALL);
  const [country, setCountry] = useState(ALL);
  const [rating, setRating] = useState(ALL);
  const [q, setQ] = useState("");
  const [key, setKey] = useState<Key>("marketValue");
  const [dir, setDir] = useState<"asc" | "desc">("desc");

  const opts = useMemo(
    () => ({
      types: uniq(rows.map((r) => r.assetType)),
      sectors: uniq(rows.map((r) => r.sector)),
      countries: uniq(rows.map((r) => r.country)),
      ratings: uniq(rows.map((r) => r.rating)),
    }),
    [rows],
  );
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const f = rows.filter(
      (r) =>
        (types.length === 0 || types.includes(r.assetType)) &&
        (sector === ALL || r.sector === sector) &&
        (country === ALL || r.country === country) &&
        (rating === ALL || r.rating === rating) &&
        (needle === "" || r.counterparty.toLowerCase().includes(needle)),
    );
    const s = dir === "asc" ? 1 : -1;
    return f.sort((a, b) => {
      const x = a[key];
      const y = b[key];
      return (
        s *
        (typeof x === "number" && typeof y === "number"
          ? x - y
          : String(x).localeCompare(String(y)))
      );
    });
  }, [rows, types, sector, country, rating, q, key, dir]);
  const totals = useMemo(
    () => ({
      n: filtered.reduce((a, r) => a + r.notional, 0),
      m: filtered.reduce((a, r) => a + r.marketValue, 0),
    }),
    [filtered],
  );
  const filtering =
    types.length > 0 || sector !== ALL || country !== ALL || rating !== ALL || q !== "";
  const reset = () => {
    setTypes([]);
    setSector(ALL);
    setCountry(ALL);
    setRating(ALL);
    setQ("");
  };

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
      <Panel
        className="lg:col-span-8"
        title={`Holdings (${filtered.length} of ${rows.length})`}
        info="Positions in the portfolio. Filter by asset type, sector, country, rating or counterparty; click a column header to sort. Totals follow the filters."
        source={source}
        actions={action}
        bodyClassName="space-y-2 p-0"
      >
        <div className="flex flex-wrap items-center gap-2 border-b border-hairline px-3 py-2">
          <div role="group" aria-label="Asset type" className="flex gap-1">
            {opts.types.map((t) => {
              const on = types.includes(t);
              return (
                <button
                  key={t}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setTypes(on ? types.filter((x) => x !== t) : [...types, t])}
                  className={cn(
                    "rounded-sm border px-2 py-0.5 text-xs outline-none focus-visible:ring-1 focus-visible:ring-ring",
                    on
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-hairline bg-paper text-foreground hover:border-primary",
                  )}
                >
                  {t}
                </button>
              );
            })}
          </div>
          <FilterSelect label="Sector" value={sector} options={opts.sectors} onChange={setSector} />
          <FilterSelect
            label="Country"
            value={country}
            options={opts.countries}
            onChange={setCountry}
          />
          <FilterSelect label="Rating" value={rating} options={opts.ratings} onChange={setRating} />
          <label className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search counterparty"
              aria-label="Search counterparty"
              className="h-7 w-44 rounded-sm border border-hairline bg-paper pl-7 pr-2 text-xs outline-none placeholder:text-muted-foreground focus-visible:ring-1 focus-visible:ring-ring"
            />
          </label>
          {filtering ? (
            <button
              type="button"
              onClick={reset}
              className="text-xs text-primary outline-none hover:underline focus-visible:underline"
            >
              Clear filters
            </button>
          ) : null}
        </div>
        {filtered.length === 0 ? (
          <EmptyState title="No holdings match" hint="Adjust or clear the filters." />
        ) : (
          <div data-lenis-prevent className="max-h-[520px] overflow-auto">
            <table className="w-full min-w-[760px] text-[12px]">
              <thead className="sticky top-0 bg-paper text-[11px] text-muted-foreground">
                <tr className="border-b border-hairline">
                  {COLS.map((c) => (
                    <th
                      key={c.k}
                      scope="col"
                      aria-sort={
                        key === c.k ? (dir === "asc" ? "ascending" : "descending") : "none"
                      }
                      className={cn("px-3 py-1 font-medium", c.right ? "text-right" : "text-left")}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          if (key === c.k) setDir(dir === "asc" ? "desc" : "asc");
                          else {
                            setKey(c.k);
                            setDir(c.right ? "desc" : "asc");
                          }
                        }}
                        className="inline-flex items-center gap-0.5 uppercase tracking-label outline-none hover:text-foreground focus-visible:text-foreground"
                      >
                        {c.label}
                        {key === c.k ? (
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
                {filtered.map((h) => (
                  <tr key={h.id} className="border-b border-hairline hover:bg-surface">
                    <td className="px-3 py-1.5">{h.assetType}</td>
                    <td className="px-3 py-1.5 text-foreground">{h.counterparty}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{h.sector}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{h.country}</td>
                    <td className="num px-3 py-1.5 text-right">{formatCurrency(h.notional)}</td>
                    <td className="num px-3 py-1.5 text-right">{formatCurrency(h.marketValue)}</td>
                    <td className="num px-3 py-1.5">{h.rating}</td>
                    <td className="num px-3 py-1.5">{formatDate(h.maturity)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="sticky bottom-0 bg-surface">
                <tr className="border-t border-hairline font-medium">
                  <td colSpan={4} className="px-3 py-1.5 text-muted-foreground">
                    Total ({filtered.length} holdings)
                  </td>
                  <td className="num px-3 py-1.5 text-right">{formatCurrency(totals.n)}</td>
                  <td className="num px-3 py-1.5 text-right">{formatCurrency(totals.m)}</td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Panel>
      <DonutPanel rows={filtered} className="lg:col-span-4" source={source} />
    </div>
  );
}

function DonutPanel({
  rows,
  className,
  source,
}: {
  rows: Holding[];
  className?: string;
  source: ProvenanceSource | undefined;
}) {
  return (
    <Panel
      className={className}
      title="Market value by asset class"
      info="Share of total market value per asset class for the holdings currently shown."
      source={source}
    >
      <AssetDonut rows={rows} />
    </Panel>
  );
}

export function PortfolioView({ action }: { action: React.ReactNode }) {
  const q = usePortfolio();
  return (
    <QueryBoundary
      query={q}
      endpoint="GET /api/portfolio"
      skeleton={<SkeletonBlock className="h-96" />}
      isEmpty={(e) => e.data.length === 0}
      emptyTitle="No holdings"
      emptyHint="The portfolio endpoint returned no positions."
    >
      {(env) => <View rows={env.data} action={action} source={env.meta.source} />}
    </QueryBoundary>
  );
}
