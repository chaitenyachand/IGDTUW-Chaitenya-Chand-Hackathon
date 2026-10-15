/** Canonical API types for the SENTINEL terminal. Keys are camelCase, timestamps ISO 8601 UTC. */

export const EVENT_TYPES = [
  "Geopolitical",
  "Macroeconomic",
  "Credit Event",
  "Merger/Acquisition",
  "Product Launch",
  "Regulatory",
  "Supply Chain",
  "Cyber",
  "Natural Disaster",
  "Market Commentary",
  "Earnings",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

export const ASSET_CLASS_KEYS = [
  "equity_index",
  "energy",
  "financials",
  "technology",
  "health_care",
  "industrials",
  "utilities",
  "staples",
  "discretionary",
  "communication",
  "banks",
  "long_treasury",
  "mid_treasury",
  "high_yield",
  "inv_grade",
  "dollar",
  "oil",
  "gold",
  "volatility",
] as const;
export type AssetClassKey = (typeof ASSET_CLASS_KEYS)[number];

export type ProvenanceSource = "live" | "replay" | "backfill" | "synthetic";
export type SignalMode = "live" | "replay" | "backfill";
export type IntegrityFlag = "single_source" | "burst" | "bot_likely" | "divergence";

/** Wrapper around every successful response. */
export interface Meta {
  source: ProvenanceSource;
  asOf: string;
  nextCursor?: string | null;
}
export interface Envelope<T> {
  data: T;
  meta: Meta;
}
export interface ApiErrorBody {
  error: { code: string; message: string };
}

export interface Signal {
  id: string;
  ts: string;
  mode: SignalMode;
  entity: string;
  ticker: string | null;
  headline: string;
  text: string;
  sourceType: "news" | "social";
  sourceName: string;
  url: string;
  /** -1..1 */
  sentiment: number;
  eventType: EventType;
  secondaryEventType: EventType | null;
  /** 1..10, null while the impact model is not live. Never treat null as 0. */
  impact: number | null;
  /** 1..10, null while the impact model is not live. */
  bookImpact: number | null;
  /** 0..1 */
  confidence: number;
  /** null while the impact model is not live. */
  halfLifeDays: number | null;
  integrity: {
    score: number;
    corroboratedBy: string[];
    flags: IntegrityFlag[];
  };
  explanation: { token: string; weight: number }[];
  affectedHoldings: { holdingId: string; estLoss: number }[];
}

export interface RiskIndex {
  value: number;
  regime: "Calm" | "Elevated" | "Stressed";
  updatedAt: string;
  series: { ts: string; value: number }[];
}

export interface PrecedentAnalog {
  eventId: string;
  title: string;
  date: string;
  similarity: number;
  region: string | null;
  maxDrawdown: number;
  recoveryDays: number | null;
  paths: Partial<Record<AssetClassKey, { day: number; ret: number }[]>>;
}
export interface PrecedentResult {
  signalId: string;
  status: "pending" | "ready" | "insufficient_data";
  n: number;
  dateRange: { from: string; to: string };
  horizonDays: number;
  analogs: PrecedentAnalog[];
  series: Partial<
    Record<
      AssetClassKey,
      {
        n: number;
        median: { day: number; ret: number }[];
        band: { day: number; p10: number; p90: number }[];
      }
    >
  >;
  halfLifeDays: number | null;
  shocks: { assetClass: AssetClassKey; median: number; p10: number; p90: number; n: number }[];
}

export interface Holding {
  id: string;
  assetType: "Loan" | "Bond" | "Derivative";
  counterparty: string;
  sector: string;
  country: string;
  notional: number;
  marketValue: number;
  rating: string;
  maturity: string;
}

export interface IndexConstituent {
  ticker: string;
  name: string;
  sector: string;
  benchmarkWeight: number;
  currentWeight: number;
  /** mean sentiment / integrity of the ticker's signals in the lookback window; null when it has none */
  sentiment: number | null;
  integrity: number | null;
  /** latest close; null when no price history is loaded */
  price: number | null;
}
export interface IndexConfig {
  mode: "auto" | "approval";
  maxWeight: number;
  minWeight: number;
  maxTurnover: number;
  sentimentThreshold: number;
  requireCorroboration: boolean;
  decay: boolean;
}
export interface WeightsResponse {
  tickers: string[];
  points: { ts: string; weights: Record<string, number> }[];
}
export interface RebalanceEvent {
  id: string;
  ts: string;
  triggerSignalId: string;
  triggerHeadline: string;
  status: "applied" | "pending" | "rejected";
  moves: { ticker: string; from: number; to: number }[];
}
export interface PerfStats {
  totalReturn: number;
  trackingError: number;
  turnover: number;
  maxDrawdown: number;
  informationRatio: number | null;
}
export interface PerformanceResponse {
  series: { ts: string; benchmark: number; tilted: number; naive: number }[];
  stats: { benchmark: PerfStats; tilted: PerfStats; naive: PerfStats };
}

export interface ScenarioShock {
  factor: string;
  value: number;
  unit: "pct" | "bps";
}
export interface Scenario {
  id: string;
  name: string;
  eventType: EventType | null;
  description: string;
  shocks: ScenarioShock[];
  armed: boolean;
}
export interface StressRule {
  id: string;
  eventType: EventType;
  minImpact: number;
  minIntegrity: number | null;
  scenarioId: string;
  enabled: boolean;
  cooldownMinutes: number;
}
export interface StressRunRequest {
  scenarioId?: string;
  shocks?: ScenarioShock[];
  mode: "calibrated" | "manual";
  signalId?: string;
}
export interface StressResult {
  scenarioId: string;
  mode: "calibrated" | "manual";
  triggeredBySignalId: string | null;
  ts: string;
  valueBefore: number;
  valueAfter: number;
  varBefore: number;
  varAfter: number;
  esBefore: number;
  esAfter: number;
  byFactor: { factor: string; delta: number }[];
  byAssetClass: { assetClass: "Loan" | "Bond" | "Derivative"; before: number; after: number }[];
  bySector: { sector: string; delta: number }[];
  byCountry: { country: string; delta: number }[];
  narrative: string;
}
export interface ReverseStressRow {
  eventType: EventType;
  loss: number;
  lossPct: number;
  onWatchlist: boolean;
}

export interface Exposure {
  byCountry: { country: string; exposure: number; stressedLoss: number }[];
  bySector: { sector: string; exposure: number; stressedLoss: number }[];
  graph: {
    nodes: { id: string; label: string; type: "counterparty" | "sector"; notional: number }[];
    edges: { source: string; target: string; weight: number }[];
  };
}

export interface Alert {
  id: string;
  ts: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  signalId: string | null;
}

/** Every scalar is null until the job that produces it has run (`make eval-test`, `train-impact`, ...): nothing is estimated. */
export interface ModelMetrics {
  modelVersion: string | null;
  trainedAt: string | null;
  sentiment: { f1: number | null; accuracy: number | null };
  event: { macroF1: number | null; labels: string[]; confusion: number[][] };
  impact: { spearman: number | null; mae: number | null };
  calibration: { ece: number | null; bins: { predicted: number; observed: number; n: number }[] };
  backtest: { quintiles: { quintile: number; meanForwardReturn: number; n: number }[] };
  drift: { threshold: number; series: { ts: string; psi: number }[] };
  latency: {
    p50Ms: number | null;
    p95Ms: number | null;
    histogram: { bucketMs: number; count: number }[];
  };
  precedentValidation: {
    maeVsNaive: number | null;
    directionalHitRate: number | null;
    bandCoverage: number | null;
  };
  card: { trainingData: string[]; knownLimitations: string[] };
}

export interface HealthSource {
  name: string;
  enabled: boolean;
  status: "ok" | "error" | "disabled" | "starting";
  lastSuccess: string | null;
  lastError: string | null;
  itemsLastRun: number;
  itemsTotal: number;
  errorCount: number;
}
export interface Health {
  status: string;
  documents: { total: number; lastHour: number; latestPublishedAt: string | null };
  sources: HealthSource[];
  queueLagSeconds?: number;
  modelVersion?: string;
}

export interface AuditEntry {
  id: string;
  ts: string;
  actor: "system" | "user";
  action: string;
  summary: string;
  payload: Record<string, unknown>;
  hash: string;
  prevHash: string | null;
}
export interface AuditVerify {
  intact: boolean;
  checked: number;
  brokenAtId: string | null;
}
export interface DemoScenario {
  id: string;
  title: string;
  description: string;
  eventDate: string;
  eventType: EventType;
}

/** Filters accepted by GET /api/signals. */
export interface SignalFilters {
  limit?: number;
  entity?: string;
  eventType?: EventType[];
  minImpact?: number;
  sourceType?: "news" | "social";
  mode?: SignalMode;
}

/** Messages pushed on /ws/signals. */
export type WsMessage =
  | { type: "hello"; id: string; data: unknown }
  | { type: "signal"; id: string; data: Signal }
  | { type: "precedent_ready"; id: string; data: { signalId: string } }
  | { type: "risk_index"; id: string; data: RiskIndex }
  | { type: "rebalance"; id: string; data: RebalanceEvent }
  | { type: "stress_run"; id: string; data: StressResult }
  | { type: "alert"; id: string; data: Alert }
  | { type: "ping"; id: string; data?: unknown };

export type WsStatus = "connecting" | "live" | "reconnecting";
