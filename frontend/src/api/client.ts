/**
 * The ONLY module the screens use to read or write data.
 * Every hook returns the TanStack Query result; `query.data` is the full
 * envelope { data, meta } so screens can render <ProvenanceBadge source={meta.source} />.
 */
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { toast } from "sonner";

import { apiGet, apiSend } from "./http";
import { ApiError } from "./errors";
import type {
  Alert,
  AuditEntry,
  AuditVerify,
  DemoScenario,
  Envelope,
  Exposure,
  Health,
  Holding,
  IndexConfig,
  IndexConstituent,
  ModelMetrics,
  PerformanceResponse,
  PrecedentResult,
  RebalanceEvent,
  ReverseStressRow,
  RiskIndex,
  Scenario,
  Signal,
  SignalFilters,
  StressResult,
  StressRule,
  StressRunRequest,
  EventType,
  WeightsResponse,
} from "./types";

export { ApiError } from "./errors";

const BASE = { retry: 1, staleTime: 10_000 } as const;

/* ------------------------------------------------------------------ signals */

export type SignalPages = InfiniteData<Envelope<Signal[]>, string | undefined>;

export function signalsKey(filters: SignalFilters) {
  return ["signals", filters] as const;
}

/** Paged list. Next page = meta.nextCursor passed back unchanged as ?cursor=; stops when it is null. */
export function useSignals(filters: SignalFilters = {}) {
  return useInfiniteQuery({
    queryKey: signalsKey(filters),
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      apiGet<Signal[]>("/api/signals", { ...filters, cursor: pageParam }, signal),
    getNextPageParam: (last) => last.meta.nextCursor ?? undefined,
    ...BASE,
  });
}

/** Flattens the pages and de-duplicates by id (live pushes can overlap a later page). */
export function flattenSignals(
  data: InfiniteData<Envelope<Signal[]>, unknown> | undefined,
): Signal[] {
  if (!data) return [];
  const seen = new Set<string>();
  const out: Signal[] = [];
  for (const page of data.pages) {
    for (const s of page.data) {
      if (seen.has(s.id)) continue;
      seen.add(s.id);
      out.push(s);
    }
  }
  return out;
}

export function useSignal(id: string | null | undefined) {
  return useQuery({
    queryKey: ["signal", id],
    queryFn: ({ signal }) =>
      apiGet<Signal>(`/api/signals/${encodeURIComponent(id as string)}`, undefined, signal),
    enabled: !!id,
    ...BASE,
  });
}

/* --------------------------------------------------------------- risk index */

export function useRiskIndex() {
  return useQuery({
    queryKey: ["risk-index"],
    queryFn: ({ signal }) => apiGet<RiskIndex>("/api/risk-index", undefined, signal),
    ...BASE,
  });
}

/* ---------------------------------------------------------------- precedent */

export function usePrecedent(signalId: string | null | undefined) {
  return useQuery({
    queryKey: ["precedent", signalId],
    queryFn: ({ signal }) =>
      apiGet<PrecedentResult>(
        `/api/precedent/${encodeURIComponent(signalId as string)}`,
        undefined,
        signal,
      ),
    enabled: !!signalId,
    // A "pending" result is completed by the WS "precedent_ready" message; poll slowly as a fallback.
    refetchInterval: (q) => (q.state.data?.data.status === "pending" ? 15_000 : false),
    ...BASE,
  });
}

/* ------------------------------------------------------------ adaptive index */

export function useConstituents() {
  return useQuery({
    queryKey: ["index", "constituents"],
    queryFn: ({ signal }) =>
      apiGet<IndexConstituent[]>("/api/index/constituents", undefined, signal),
    ...BASE,
  });
}
export function useIndexWeights(range: { from?: string; to?: string } = {}) {
  return useQuery({
    queryKey: ["index", "weights", range],
    queryFn: ({ signal }) => apiGet<WeightsResponse>("/api/index/weights", range, signal),
    ...BASE,
  });
}
export function useRebalances() {
  return useQuery({
    queryKey: ["index", "rebalances"],
    queryFn: ({ signal }) => apiGet<RebalanceEvent[]>("/api/index/rebalances", undefined, signal),
    ...BASE,
  });
}
export function useIndexPerformance() {
  return useQuery({
    queryKey: ["index", "performance"],
    queryFn: ({ signal }) =>
      apiGet<PerformanceResponse>("/api/index/performance", undefined, signal),
    ...BASE,
  });
}
export function useIndexConfig() {
  return useQuery({
    queryKey: ["index", "config"],
    queryFn: ({ signal }) => apiGet<IndexConfig>("/api/index/config", undefined, signal),
    ...BASE,
  });
}

function errMsg(e: unknown) {
  return e instanceof ApiError
    ? `${e.endpoint}: ${e.message}`
    : e instanceof Error
      ? e.message
      : "Request failed";
}

export function useSaveIndexConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cfg: IndexConfig) => apiSend<IndexConfig>("POST", "/api/index/config", cfg),
    onSuccess: () => {
      toast.success("Index configuration saved");
      void qc.invalidateQueries({ queryKey: ["index"] });
    },
    onError: (e) => toast.error("Could not save configuration", { description: errMsg(e) }),
  });
}
export function useRebalanceDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" }) =>
      apiSend<RebalanceEvent>(
        "POST",
        `/api/index/rebalances/${encodeURIComponent(id)}/${decision}`,
      ),
    onSuccess: (_r, v) => {
      toast.success(v.decision === "approve" ? "Rebalance approved" : "Rebalance rejected");
      void qc.invalidateQueries({ queryKey: ["index"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: (e) => toast.error("Could not update rebalance", { description: errMsg(e) }),
  });
}

/* ---------------------------------------------------------------- portfolio */

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: ({ signal }) => apiGet<Holding[]>("/api/portfolio", undefined, signal),
    ...BASE,
  });
}
export function useExposure() {
  return useQuery({
    queryKey: ["portfolio", "exposure"],
    queryFn: ({ signal }) => apiGet<Exposure>("/api/portfolio/exposure", undefined, signal),
    ...BASE,
  });
}

/* ------------------------------------------------------------------- stress */

export function useScenarios() {
  return useQuery({
    queryKey: ["stress", "scenarios"],
    queryFn: ({ signal }) => apiGet<Scenario[]>("/api/stress/scenarios", undefined, signal),
    ...BASE,
  });
}
export function useStressRules() {
  return useQuery({
    queryKey: ["stress", "rules"],
    queryFn: ({ signal }) => apiGet<StressRule[]>("/api/stress/rules", undefined, signal),
    ...BASE,
  });
}
export function useReverseStress() {
  return useQuery({
    queryKey: ["stress", "reverse"],
    queryFn: ({ signal }) => apiGet<ReverseStressRow[]>("/api/stress/reverse", undefined, signal),
    ...BASE,
  });
}

/** The most recent stress result seen this session (from a run or the WS "stress_run" push). Never fetched. */
export function useLastStressRun() {
  return useQuery<Envelope<StressResult> | null>({
    queryKey: ["stress", "lastRun"],
    queryFn: () => null,
    enabled: false,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function useRunStress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: StressRunRequest) => apiSend<StressResult>("POST", "/api/stress/run", req),
    onSuccess: (res) => {
      qc.setQueryData(["stress", "lastRun"], res);
      void qc.invalidateQueries({ queryKey: ["audit"] });
      toast.success("Stress run complete");
    },
    onError: (e) => toast.error("Stress run failed", { description: errMsg(e) }),
  });
}
export function useUpsertStressRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rule: StressRule) => apiSend<StressRule>("POST", "/api/stress/rules", rule),
    onSuccess: () => {
      toast.success("Rule saved");
      void qc.invalidateQueries({ queryKey: ["stress"] });
    },
    onError: (e) => toast.error("Could not save rule", { description: errMsg(e) }),
  });
}
export function useDeleteStressRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiSend<unknown>("DELETE", `/api/stress/rules/${encodeURIComponent(id)}`),
    onSuccess: () => {
      toast.success("Rule deleted");
      void qc.invalidateQueries({ queryKey: ["stress"] });
    },
    onError: (e) => toast.error("Could not delete rule", { description: errMsg(e) }),
  });
}
export function useWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { eventType: EventType; onWatchlist: boolean }) =>
      apiSend<unknown>("POST", "/api/stress/watchlist", body),
    onSuccess: (_r, v) => {
      toast.success(
        v.onWatchlist
          ? `${v.eventType} added to watchlist`
          : `${v.eventType} removed from watchlist`,
      );
      void qc.invalidateQueries({ queryKey: ["stress", "reverse"] });
    },
    onError: (e) => toast.error("Could not update watchlist", { description: errMsg(e) }),
  });
}

/* -------------------------------------------------------- model, health, etc */

export function useModelMetrics() {
  return useQuery({
    queryKey: ["model", "metrics"],
    queryFn: ({ signal }) => apiGet<ModelMetrics>("/api/model/metrics", undefined, signal),
    ...BASE,
  });
}
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiGet<Health>("/api/health", undefined, signal),
    refetchInterval: 30_000,
    ...BASE,
  });
}
export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: ({ signal }) => apiGet<Alert[]>("/api/alerts", undefined, signal),
    ...BASE,
  });
}

/* -------------------------------------------------------------------- audit */

export function useAudit() {
  return useInfiniteQuery({
    queryKey: ["audit", "ledger"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      apiGet<AuditEntry[]>("/api/audit", { cursor: pageParam }, signal),
    getNextPageParam: (last) => last.meta.nextCursor ?? undefined,
    ...BASE,
  });
}
export function flattenAudit(data: InfiniteData<Envelope<AuditEntry[]>, unknown> | undefined) {
  if (!data) return [] as AuditEntry[];
  const seen = new Set<string>();
  const out: AuditEntry[] = [];
  for (const p of data.pages)
    for (const e of p.data) {
      if (seen.has(e.id)) continue;
      seen.add(e.id);
      out.push(e);
    }
  return out;
}
export function useVerifyAudit() {
  return useMutation({
    mutationFn: () => apiGet<AuditVerify>("/api/audit/verify"),
    onError: (e) => toast.error("Verification failed", { description: errMsg(e) }),
  });
}

/* --------------------------------------------------------------------- demo */

export function useDemoScenarios() {
  return useQuery({
    queryKey: ["demo", "scenarios"],
    queryFn: ({ signal }) => apiGet<DemoScenario[]>("/api/demo/scenarios", undefined, signal),
    ...BASE,
  });
}
export function useInjectDemo() {
  return useMutation({
    mutationFn: (scenarioId: string) =>
      apiSend<unknown>("POST", "/api/demo/inject", { scenarioId }),
    onSuccess: () =>
      toast.success("Replaying archived event", {
        description: "Resulting signals arrive as REPLAY.",
      }),
    onError: (e) => toast.error("Could not start replay", { description: errMsg(e) }),
  });
}
