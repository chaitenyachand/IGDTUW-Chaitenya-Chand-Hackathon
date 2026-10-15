import { ChevronDown, Search, X } from "lucide-react";

import { EVENT_TYPES, type EventType } from "@/api/types";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { RangeSlider } from "./range-slider";

export type SourceFilter = "all" | "news" | "social";

export interface FilterState {
  entity: string;
  source: SourceFilter;
  types: EventType[];
  impact: [number, number];
  sentiment: [number, number];
  integrity: number;
}

export const IMPACT_FULL: [number, number] = [1, 10];
export const SENTIMENT_FULL: [number, number] = [-1, 1];

export const DEFAULT_FILTERS: FilterState = {
  entity: "",
  source: "all",
  types: [],
  impact: IMPACT_FULL,
  sentiment: SENTIMENT_FULL,
  integrity: 0,
};

export const impactActive = (f: FilterState) =>
  f.impact[0] > IMPACT_FULL[0] || f.impact[1] < IMPACT_FULL[1];

export function filtersAreDefault(f: FilterState) {
  return (
    f.entity.trim() === "" &&
    f.source === "all" &&
    f.types.length === 0 &&
    !impactActive(f) &&
    f.sentiment[0] === SENTIMENT_FULL[0] &&
    f.sentiment[1] === SENTIMENT_FULL[1] &&
    f.integrity === 0
  );
}

const SOURCES: { key: SourceFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "news", label: "News" },
  { key: "social", label: "Social" },
];

export function FilterBar({
  value,
  onChange,
}: {
  value: FilterState;
  onChange: (f: FilterState) => void;
}) {
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });
  const toggleType = (t: EventType) =>
    set({
      types: value.types.includes(t) ? value.types.filter((x) => x !== t) : [...value.types, t],
    });

  return (
    <div className="sticky top-0 z-20 -mx-1 border-b border-hairline bg-paper/95 px-1 py-3 backdrop-blur">
      <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
        <label className="relative block w-56">
          <span className="sr-only">Search entity or ticker</span>
          <Search className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={value.entity}
            onChange={(e) => set({ entity: e.target.value })}
            placeholder="Entity or ticker"
            className="h-8 pl-7 pr-7 text-[13px]"
          />
          {value.entity ? (
            <button
              type="button"
              aria-label="Clear entity search"
              onClick={() => set({ entity: "" })}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-sm p-0.5 text-muted-foreground hover:text-foreground"
            >
              <X className="size-3" />
            </button>
          ) : null}
        </label>

        <div
          role="group"
          aria-label="Source type"
          className="inline-flex overflow-hidden rounded-sm border border-hairline"
        >
          {SOURCES.map((s) => (
            <button
              key={s.key}
              type="button"
              aria-pressed={value.source === s.key}
              onClick={() => set({ source: s.key })}
              className={cn(
                "h-8 px-3 text-xs outline-none transition-colors focus-visible:ring-1 focus-visible:ring-ring",
                value.source === s.key
                  ? "bg-primary text-primary-foreground"
                  : "bg-paper text-foreground hover:bg-surface",
              )}
            >
              {s.label}
            </button>
          ))}
        </div>

        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-hairline bg-paper px-2.5 text-xs outline-none hover:bg-surface focus-visible:ring-1 focus-visible:ring-ring"
            >
              Event type
              <span className="num rounded-sm bg-surface px-1 text-[11px] text-muted-foreground">
                {value.types.length === 0 ? "all" : value.types.length}
              </span>
              <ChevronDown className="size-3 text-muted-foreground" />
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64 p-2">
            <div className="mb-1 flex items-center justify-between px-1 text-[11px] uppercase tracking-label text-muted-foreground">
              <span>Event types</span>
              <button
                type="button"
                onClick={() => set({ types: [] })}
                className="normal-case tracking-normal hover:text-primary"
              >
                Clear
              </button>
            </div>
            <ul className="space-y-0.5" role="group" aria-label="Event types">
              {EVENT_TYPES.map((t) => (
                <li key={t}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-sm px-1 py-1 text-[13px] hover:bg-surface">
                    <Checkbox
                      checked={value.types.includes(t)}
                      onCheckedChange={() => toggleType(t)}
                      className="size-3.5"
                    />
                    {t}
                  </label>
                </li>
              ))}
            </ul>
          </PopoverContent>
        </Popover>

        <RangeSlider
          className="w-44"
          label="Impact"
          info="Model impact score, 1 to 10. Signals without a score (impact model not live) are hidden whenever this range is narrowed."
          min={1}
          max={10}
          step={0.5}
          value={value.impact}
          onChange={(v) => set({ impact: [v[0] ?? 1, v[1] ?? 10] })}
          format={(n) => formatNumber(n, { maximumFractionDigits: 1 })}
        />
        <RangeSlider
          className="w-44"
          label="Sentiment"
          info="Sentiment from -1 (negative) to +1 (positive)."
          min={-1}
          max={1}
          step={0.05}
          value={value.sentiment}
          onChange={(v) => set({ sentiment: [v[0] ?? -1, v[1] ?? 1] })}
          format={(n) => formatNumber(n, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        />
        <RangeSlider
          className="w-36"
          label="Min integrity"
          info="Hide signals whose source-integrity score (0 to 1) is below this value."
          min={0}
          max={1}
          step={0.05}
          value={[value.integrity]}
          onChange={(v) => set({ integrity: v[0] ?? 0 })}
          format={(n) => n.toFixed(2)}
        />
      </div>
    </div>
  );
}
