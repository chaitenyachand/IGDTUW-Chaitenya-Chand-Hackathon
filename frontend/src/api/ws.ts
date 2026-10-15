/**
 * Live feed over WebSocket (VITE_WS_URL, wss://host/ws/signals).
 * - connects with ?since=<lastEventId>&minImpact=<n>
 * - reconnects with exponential backoff (1s .. 30s) and replays missed events via `since`
 * - merges messages into the TanStack Query cache
 */
import { useEffect, useSyncExternalStore } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { WS_URL } from "./config";
import { getSettings } from "@/lib/settings";
import { signalsKey, type SignalPages } from "./client";
import type {
  Alert,
  Envelope,
  Meta,
  RebalanceEvent,
  RiskIndex,
  Signal,
  SignalFilters,
  StressResult,
  WsMessage,
  WsStatus,
} from "./types";

/* ---------- connection status store ---------- */
let status: WsStatus = "connecting";
const statusListeners = new Set<() => void>();
function setStatus(s: WsStatus) {
  if (status === s) return;
  status = s;
  statusListeners.forEach((l) => l());
}
export function useWsStatus(): WsStatus {
  return useSyncExternalStore(
    (l) => {
      statusListeners.add(l);
      return () => statusListeners.delete(l);
    },
    () => status,
    () => "connecting" as WsStatus,
  );
}

/* ---------- filter matching for merging into filtered caches ---------- */
export function signalMatches(s: Signal, f: SignalFilters): boolean {
  if (f.entity && !`${s.entity} ${s.ticker ?? ""}`.toLowerCase().includes(f.entity.toLowerCase()))
    return false;
  if (f.eventType?.length && !f.eventType.includes(s.eventType)) return false;
  if (f.minImpact != null && (s.impact == null || s.impact < f.minImpact)) return false;
  if (f.sourceType && s.sourceType !== f.sourceType) return false;
  if (f.mode && s.mode !== f.mode) return false;
  return true;
}

function upsertById<T extends { id: string }>(list: T[] | undefined, item: T, prepend = true): T[] {
  const rest = (list ?? []).filter((x) => x.id !== item.id);
  return prepend ? [item, ...rest] : [...rest, item];
}

function mergeSignal(qc: QueryClient, sig: Signal) {
  qc.setQueryData(["signal", sig.id], (old: Envelope<Signal> | undefined) =>
    old
      ? { ...old, data: sig }
      : { data: sig, meta: { source: sig.mode, asOf: sig.ts } satisfies Meta },
  );
  for (const [key, data] of qc.getQueriesData<SignalPages>({ queryKey: ["signals"] })) {
    if (!data || !data.pages.length) continue;
    const filters = (key[1] ?? {}) as SignalFilters;
    if (!signalMatches(sig, filters)) continue;
    const [first, ...rest] = data.pages;
    if (!first) continue;
    const next: SignalPages = {
      ...data,
      pages: [{ ...first, data: upsertById(first.data, sig) }, ...rest],
    };
    qc.setQueryData(signalsKey(filters), next);
  }
}

function handle(qc: QueryClient, msg: WsMessage) {
  switch (msg.type) {
    case "signal":
      mergeSignal(qc, msg.data);
      break;
    case "precedent_ready":
      void qc.invalidateQueries({ queryKey: ["precedent", msg.data.signalId] });
      break;
    case "risk_index":
      qc.setQueryData(["risk-index"], (old: Envelope<RiskIndex> | undefined) => ({
        data: msg.data as RiskIndex,
        meta: old?.meta ?? ({ source: "live", asOf: msg.data.updatedAt } satisfies Meta),
      }));
      break;
    case "rebalance":
      qc.setQueryData(["index", "rebalances"], (old: Envelope<RebalanceEvent[]> | undefined) =>
        old ? { ...old, data: upsertById(old.data, msg.data as RebalanceEvent) } : old,
      );
      for (const k of ["constituents", "weights", "performance"])
        void qc.invalidateQueries({ queryKey: ["index", k] });
      break;
    case "stress_run":
      qc.setQueryData(["stress", "lastRun"], {
        data: msg.data as StressResult,
        meta: { source: "live", asOf: (msg.data as StressResult).ts } satisfies Meta,
      });
      break;
    case "alert": {
      const alert = msg.data as Alert;
      qc.setQueryData(["alerts"], (old: Envelope<Alert[]> | undefined) =>
        old ? { ...old, data: upsertById(old.data, alert) } : old,
      );
      if (alert.severity !== "info") toast.warning(alert.title, { description: alert.message });
      break;
    }
    default:
      break;
  }
}

/* ---------- singleton socket ---------- */
let lastEventId: string | null = null;

/**
 * Mount ONCE (the terminal shell does). Keeps the socket open and the query cache current.
 */
export function useLiveSignals() {
  const qc = useQueryClient();

  useEffect(() => {
    if (!WS_URL) return;
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let closed = false;
    let lastMinImpact = getSettings().minImpact;

    const connect = () => {
      if (closed) return;
      setStatus(attempt === 0 ? "connecting" : "reconnecting");
      const url = new URL(WS_URL);
      if (lastEventId) url.searchParams.set("since", lastEventId);
      const mi = getSettings().minImpact;
      if (mi != null) url.searchParams.set("minImpact", String(mi));
      lastMinImpact = mi;
      try {
        ws = new WebSocket(url.toString());
      } catch {
        schedule();
        return;
      }
      ws.onopen = () => {
        attempt = 0;
        setStatus("live");
      };
      ws.onmessage = (ev) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(String(ev.data)) as WsMessage;
        } catch {
          return;
        }
        if (msg.type !== "ping" && msg.type !== "hello" && msg.id) lastEventId = msg.id;
        handle(qc, msg);
      };
      ws.onclose = () => {
        if (!closed) schedule();
      };
      ws.onerror = () => ws?.close();
    };

    const schedule = () => {
      setStatus("reconnecting");
      const delay = Math.min(30_000, 1000 * 2 ** attempt);
      attempt += 1;
      timer = setTimeout(connect, delay);
    };

    connect();

    // Reconnect when the minImpact preference changes.
    const poll = setInterval(() => {
      if (getSettings().minImpact !== lastMinImpact) {
        ws?.close();
      }
    }, 1500);

    return () => {
      closed = true;
      clearInterval(poll);
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [qc]);
}
