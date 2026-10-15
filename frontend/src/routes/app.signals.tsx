import { useCallback, useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { flattenSignals, useSignals } from "@/api/client";
import type { EventType, SignalFilters } from "@/api/types";
import { useSettings } from "@/lib/settings";
import { EmptyState, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import {
  DEFAULT_FILTERS,
  FilterBar,
  impactActive,
  type FilterState,
} from "@/components/terminal/signals/filter-bar";
import {
  SignalTable,
  sortSignals,
  type SortKey,
  type SortState,
} from "@/components/terminal/signals/signal-table";

export const Route = createFileRoute("/app/signals")({
  head: () => ({ meta: [{ title: "Signal Explorer — SENTINEL Terminal" }] }),
  validateSearch: (s: Record<string, unknown>) => ({
    entity: typeof s["entity"] === "string" ? s["entity"] : undefined,
  }),
  component: SignalExplorer,
});

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function SignalExplorer() {
  const search = Route.useSearch();
  const { tz } = useSettings();
  const [filters, setFilters] = useState<FilterState>({
    ...DEFAULT_FILTERS,
    entity: search.entity ?? "",
  });
  const [sort, setSort] = useState<SortState>({ key: "time", dir: "desc" });

  // The command palette can navigate here with a new ?entity= while the route stays mounted.
  useEffect(() => {
    if (search.entity !== undefined)
      setFilters((f) => (f.entity === search.entity ? f : { ...f, entity: search.entity ?? "" }));
  }, [search.entity]);

  const entity = useDebounced(filters.entity.trim(), 300);
  const server: SignalFilters = useMemo(() => {
    const f: SignalFilters = { limit: 100 };
    if (entity) f.entity = entity;
    if (filters.types.length) f.eventType = filters.types as EventType[];
    if (filters.impact[0] > 1) f.minImpact = filters.impact[0];
    if (filters.source !== "all") f.sourceType = filters.source;
    return f;
  }, [entity, filters.types, filters.impact, filters.source]);

  const query = useSignals(server);
  const all = useMemo(() => flattenSignals(query.data), [query.data]);

  const rows = useMemo(() => {
    const narrowed = impactActive(filters);
    const filtered = all.filter((s) => {
      if (s.sentiment < filters.sentiment[0] || s.sentiment > filters.sentiment[1]) return false;
      if (s.integrity.score < filters.integrity) return false;
      if (narrowed) {
        if (s.impact == null) return false;
        if (s.impact < filters.impact[0] || s.impact > filters.impact[1]) return false;
      }
      return true;
    });
    return sortSignals(filtered, sort);
  }, [all, filters, sort]);

  const onSort = useCallback(
    (key: SortKey) =>
      setSort((s) =>
        s.key === key
          ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
          : {
              key,
              dir:
                key === "entity" || key === "headline" || key === "event" || key === "source"
                  ? "asc"
                  : "desc",
            },
      ),
    [],
  );
  const fetchNext = useCallback(() => void query.fetchNextPage(), [query]);
  const firstSource = query.data?.pages[0]?.meta.source;

  return (
    <div className="space-y-3 p-4 text-[13px]">
      <FilterBar value={filters} onChange={setFilters} />
      <Panel
        title="Signal Explorer"
        info="Every scored news and social item. Entity, event type, source and minimum impact are filtered by the server; the sentiment range, impact maximum and minimum integrity are applied to the loaded rows."
        source={firstSource}
        bodyClassName="p-0"
        actions={
          query.data ? (
            <span className="num text-[11px] text-muted-foreground">
              {rows.length.toLocaleString("en-US")} rows
              {rows.length !== all.length ? ` of ${all.length.toLocaleString("en-US")} loaded` : ""}
            </span>
          ) : null
        }
      >
        <QueryBoundary
          query={query}
          endpoint="GET /api/signals"
          skeleton={<SkeletonBlock lines={10} className="p-3" />}
        >
          {() =>
            rows.length === 0 && !query.hasNextPage ? (
              <EmptyState
                title="No signals match these filters"
                hint="Widen the impact, sentiment or integrity ranges, or search a different entity."
                className="py-16"
              />
            ) : (
              <SignalTable
                rows={rows}
                sort={sort}
                onSort={onSort}
                tz={tz}
                hasNextPage={!!query.hasNextPage}
                isFetchingNext={query.isFetchingNextPage}
                fetchNext={fetchNext}
              />
            )
          }
        </QueryBoundary>
        {query.data && rows.length === 0 && !query.hasNextPage ? (
          <div className="flex justify-center pb-6">
            <button
              type="button"
              onClick={() => setFilters(DEFAULT_FILTERS)}
              className="rounded-sm border border-hairline px-3 py-1 text-xs hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring"
            >
              Clear filters
            </button>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
