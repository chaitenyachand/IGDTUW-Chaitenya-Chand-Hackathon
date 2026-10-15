"""Stress Lab service: runtime cache, shock resolution, persistence, trigger rules, watchlist and alerts."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from ..audit import ledger
from ..events import publish
from ..portfolio.pricing import MarketDataMissing
from ..precedent.engine import Library, aggregate
from ..precedent.service import precedent_for_signal
from ..taxonomy import EVENT_TYPES
from ..portfolio.pricing import apply_shocks
from . import credit
from . import engine as se

log = logging.getLogger(__name__)
WATCHLIST_IMPACT_DISCOUNT = 1.0          # an event type on the watchlist fires its rules this many impact points earlier
REFRESH_SECONDS = 900
CALIBRATED = "calibrated"
DEFAULT_RULES = [
    ("Geopolitical", 7.0, 0.6), ("Credit Event", 6.5, 0.6), ("Macroeconomic", 7.0, 0.6), ("Cyber", 7.5, 0.6),
]


class StressError(ValueError):
    """A request the engine cannot honour (400/422 in the API)."""


class StressRuntime:
    """Market context + PRECEDENT library, reloaded every 15 minutes; the baseline VaR is computed once per load."""

    def __init__(self, ctx: se.Context, lib: Library):
        self.ctx, self.lib, self.loaded_at = ctx, lib, time.time()
        self._var = None

    @classmethod
    async def load(cls, pool):
        return cls(await se.load_context(pool), await Library.load(pool))

    def var_before(self):
        if self._var is None:
            self._var = se.var_es(self.ctx.book, self.ctx.state, self.ctx.hist)
        return self._var

    def stale(self) -> bool:
        return time.time() - self.loaded_at > REFRESH_SECONDS


class RuntimeHolder:
    """Lazy, refreshing holder used by the API and the workers. `get` raises MarketDataMissing when data is absent."""

    def __init__(self, pool):
        self.pool, self.rt, self._lock = pool, None, asyncio.Lock()

    async def get(self) -> StressRuntime:
        async with self._lock:
            if self.rt is None or self.rt.stale():
                self.rt = await StressRuntime.load(self.pool)
            return self.rt


def _shock_dict(shocks) -> dict:
    if isinstance(shocks, dict):
        return {k: float(v) for k, v in shocks.items() if v is not None}
    return {s["factor"]: float(s["value"]) for s in shocks or []}


async def resolve(pool, rt: StressRuntime, req: dict) -> tuple:
    """-> (detail shocks, scenario_id, display name, mode, signal_id)."""
    signal_id, scenario_id, mode = req.get("signalId"), req.get("scenarioId"), req.get("mode")
    if (mode == "calibrated" and (signal_id or not scenario_id)) or (signal_id and not req.get("shocks") and not scenario_id):
        if not signal_id:
            raise StressError("calibrated mode needs signalId")
        try:
            _, analogs = await precedent_for_signal(pool, rt.lib, signal_id)
        except KeyError:
            raise StressError(f"unknown signal {signal_id}")
        if not analogs:
            raise StressError("PRECEDENT found no analogs for this signal, so there is no calibrated shock vector")
        vals = se.aggregate_values(aggregate(analogs))
        if vals["equity"] is None or vals["dgs10"] is None:
            raise StressError("PRECEDENT analogs lack equity or rate outcomes")
        return se.shocks_from_values(vals, rt.ctx), f"{CALIBRATED}:{signal_id}", "PRECEDENT-calibrated shock", "calibrated", signal_id
    if req.get("shocks") and mode == "manual":                  # the terminal's sliders: the user's shocks win; the scenario id only labels the run
        ui = _shock_dict(req["shocks"])
        label = next((e.title for e in rt.lib.events if e.id == scenario_id), None) if scenario_id else None
        return (se.expand_ui_shocks(ui, rt.ctx), scenario_id or "manual",
                f"manual shock (started from '{label}')" if label else "manual shock", "manual", signal_id)
    if scenario_id and scenario_id != "manual":
        ev = next((e for e in rt.lib.events if e.id == scenario_id), None)
        if ev is None:
            raise StressError(f"unknown scenario {scenario_id}")
        vals = se.event_values(ev)
        if vals["equity"] is None or vals["dgs10"] is None:
            raise StressError("scenario has no equity or rate outcome")
        return se.shocks_from_values(vals, rt.ctx), ev.id, ev.title, "calibrated", signal_id      # realised moves of a real event
    if req.get("shocks"):
        ui = _shock_dict(req["shocks"])
        return se.expand_ui_shocks(ui, rt.ctx), "manual", "manual shock", "manual", signal_id
    raise StressError("provide scenarioId, shocks, or signalId")


def result_summary(res: dict) -> dict:
    keys = ("id", "scenarioId", "mode", "triggeredBySignalId", "ts", "valueBefore", "valueAfter", "varBefore", "varAfter",
            "esBefore", "esAfter", "narrative")
    return {k: res[k] for k in keys if k in res}


async def execute(pool, redis, rt: StressRuntime, req: dict, actor: str = "api", source: str = "live",
                  now: datetime | None = None, signal_id: str | None = None) -> dict:
    detail, scenario_id, name, mode, sig = await resolve(pool, rt, {**req, **({"signalId": signal_id} if signal_id else {})})
    vb = await asyncio.to_thread(rt.var_before)
    res = await asyncio.to_thread(se.run_stress, rt.ctx, detail, scenario_id, mode, name, sig, vb)
    now = now or datetime.now(timezone.utc)
    res["id"], res["ts"], res["source"] = f"sr-{uuid.uuid4().hex[:12]}", now.isoformat(), source
    res["appliedShocks"] = {k: float(v) for k, v in detail.items()}
    res["expectedLoss"] = credit.expected_loss(rt.ctx.book, rt.ctx.state, apply_shocks(rt.ctx.state, detail))
    res["narrative"] = f"{res['narrative']} {credit.sentence(res['expectedLoss'])}"
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute("INSERT INTO stress_runs (id, ts, scenario_id, mode, triggered_by_signal_id, result, source) "
                              "VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7)", res["id"], now, res["scenarioId"], mode, sig,
                              json.dumps(res), source)
            d = (res["valueAfter"] - res["valueBefore"]) / abs(res["valueBefore"]) * 100 if res["valueBefore"] else 0.0
            await ledger.append_con(con, actor, "stress_run", f"Stress run '{name}': book {d:+.2f}%",
                                    {"runId": res["id"], "scenarioId": res["scenarioId"], "mode": mode, "source": source,
                                     "triggeredBySignalId": sig, "valueBefore": res["valueBefore"], "valueAfter": res["valueAfter"],
                                     "varAfter": res["varAfter"]}, ts=now)
    await publish(redis, "stress_run", {k: v for k, v in res.items() if k not in ("appliedShocks", "expectedLoss")}, source)
    return res


# ---------- rules ----------
def rule_api(r) -> dict:
    return {"id": r["id"], "eventType": r["event_type"], "minImpact": r["min_impact"], "minIntegrity": r["min_integrity"],
            "scenarioId": r["scenario_id"], "enabled": r["enabled"], "cooldownMinutes": r["cooldown_minutes"],
            "lastFired": r["last_fired"].isoformat() if r["last_fired"] else None}


async def list_rules(pool) -> list:
    return [rule_api(r) for r in await pool.fetch("SELECT * FROM stress_rules ORDER BY event_type, id")]


async def validate_rule(pool, d: dict, lib: Library | None) -> dict:
    if d.get("eventType") not in EVENT_TYPES:
        raise StressError(f"eventType must be one of {EVENT_TYPES}")
    mi = float(d.get("minImpact", 0))
    if not 0 <= mi <= 10:
        raise StressError("minImpact must be between 0 and 10")
    mg = d.get("minIntegrity")
    if mg is not None and not 0 <= float(mg) <= 1:
        raise StressError("minIntegrity must be between 0 and 1")
    sc = d.get("scenarioId") or CALIBRATED
    if sc != CALIBRATED and lib is not None and not any(e.id == sc for e in lib.events):
        raise StressError(f"unknown scenario {sc}")
    cd = int(d.get("cooldownMinutes", 60))
    if cd < 0:
        raise StressError("cooldownMinutes must be >= 0")
    return {"event_type": d["eventType"], "min_impact": mi, "min_integrity": None if mg is None else float(mg),
            "scenario_id": sc, "enabled": bool(d.get("enabled", True)), "cooldown_minutes": cd}


async def save_rule(pool, d: dict, lib, rule_id: str | None = None, actor: str = "api", upsert: bool = False) -> dict:
    """rule_id given: update it (KeyError when missing), or with upsert=True create it under that id. No rule_id: create one."""
    v = await validate_rule(pool, d, lib)
    async with pool.acquire() as con:
        async with con.transaction():
            if rule_id and upsert and not await con.fetchval("SELECT 1 FROM stress_rules WHERE id=$1", rule_id):
                await con.execute("INSERT INTO stress_rules (id, event_type, min_impact, min_integrity, scenario_id, enabled, cooldown_minutes) "
                                  "VALUES ($1,$2,$3,$4,$5,$6,$7)", rule_id, *v.values())
                action = "rule_created"
            elif rule_id:
                if not await con.fetchval("SELECT 1 FROM stress_rules WHERE id=$1", rule_id):
                    raise KeyError(rule_id)
                await con.execute("UPDATE stress_rules SET event_type=$2, min_impact=$3, min_integrity=$4, scenario_id=$5, "
                                  "enabled=$6, cooldown_minutes=$7 WHERE id=$1", rule_id, *v.values())
                action = "rule_updated"
            else:
                rule_id = f"rule-{uuid.uuid4().hex[:8]}"
                await con.execute("INSERT INTO stress_rules (id, event_type, min_impact, min_integrity, scenario_id, enabled, cooldown_minutes) "
                                  "VALUES ($1,$2,$3,$4,$5,$6,$7)", rule_id, *v.values())
                action = "rule_created"
            await ledger.append_con(con, actor, action, f"Stress rule {rule_id}: {v['event_type']} impact > {v['min_impact']:g}",
                                    {"ruleId": rule_id, **v})
            return rule_api(await con.fetchrow("SELECT * FROM stress_rules WHERE id=$1", rule_id))


async def delete_rule(pool, rule_id: str, actor: str = "api"):
    async with pool.acquire() as con:
        async with con.transaction():
            n = await con.fetchval("WITH d AS (DELETE FROM stress_rules WHERE id=$1 RETURNING 1) SELECT count(*) FROM d", rule_id)
            if not n:
                raise KeyError(rule_id)
            await ledger.append_con(con, actor, "rule_deleted", f"Stress rule {rule_id} deleted", {"ruleId": rule_id})


async def ensure_default_rules(pool) -> int:
    if await pool.fetchval("SELECT count(*) FROM stress_rules"):
        return 0
    await pool.executemany(
        "INSERT INTO stress_rules (id, event_type, min_impact, min_integrity, scenario_id, enabled, cooldown_minutes) "
        "VALUES ($1,$2,$3,$4,$5,TRUE,60)", [(f"default-{et.lower().replace(' ', '-')}", et, mi, mg, CALIBRATED) for et, mi, mg in DEFAULT_RULES])
    return len(DEFAULT_RULES)


# ---------- watchlist ----------
async def get_watchlist(pool) -> list:
    return [r["event_type"] for r in await pool.fetch("SELECT event_type FROM stress_watchlist ORDER BY event_type")]


async def set_watchlist(pool, types: list, actor: str = "api") -> list:
    bad = [t for t in types if t not in EVENT_TYPES]
    if bad:
        raise StressError(f"unknown event types {bad}")
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute("DELETE FROM stress_watchlist")
            await con.executemany("INSERT INTO stress_watchlist (event_type) VALUES ($1)", [(t,) for t in sorted(set(types))])
            await ledger.append_con(con, actor, "watchlist_change", f"Watchlist set to {sorted(set(types))}", {"eventTypes": sorted(set(types))})
    return await get_watchlist(pool)


# ---------- alerts ----------
def alert_api(r) -> dict:
    return {"id": r["id"], "ts": r["ts"].isoformat(), "severity": r["severity"], "title": r["title"], "message": r["message"],
            "signalId": r["signal_id"], "source": r["source"]}


async def list_alerts(pool, source: str = "live", limit: int = 50) -> list:
    return [alert_api(r) for r in await pool.fetch("SELECT * FROM alerts WHERE source=$1 ORDER BY ts DESC LIMIT $2", source, limit)]


def severity(res: dict) -> str:
    loss = (res["valueBefore"] - res["valueAfter"]) / abs(res["valueBefore"]) if res["valueBefore"] else 0.0
    return "critical" if loss >= 0.03 else ("high" if loss >= 0.01 else ("medium" if loss > 0 else "info"))


_replay_cooldown: dict = {}      # replayed time is not wall-clock time: replay cooldowns are tracked in memory, per process


async def evaluate_rules(pool, redis, holder: RuntimeHolder, sig: dict, source: str = "live", now: datetime | None = None) -> list:
    """Run every enabled rule that matches this signal. Returns the stress runs that fired."""
    if sig.get("impact") is None:
        return []
    rules = await pool.fetch("SELECT * FROM stress_rules WHERE enabled AND event_type = $1", sig["eventType"])
    if not rules:
        return []
    watch = set(await get_watchlist(pool))
    now = now or datetime.now(timezone.utc)
    fired = []
    for r in rules:
        thr = r["min_impact"] - (WATCHLIST_IMPACT_DISCOUNT if r["event_type"] in watch else 0.0)
        if sig["impact"] <= thr:
            continue
        if r["min_integrity"] is not None and sig["integrity"]["score"] <= r["min_integrity"]:
            continue
        gap = timedelta(minutes=r["cooldown_minutes"])
        if source == "replay":
            last = _replay_cooldown.get(r["id"])
            if last is not None and timedelta(0) <= now - last < gap:      # time going backwards = a new replay: not a cooldown
                continue
        elif r["last_fired"] is not None and now - r["last_fired"] < gap:
            continue
        try:
            rt = await holder.get()
            req = ({"mode": "calibrated"} if r["scenario_id"] == CALIBRATED else {"scenarioId": r["scenario_id"]})
            res = await execute(pool, redis, rt, req, actor=f"rule:{r['id']}", source=source, now=now, signal_id=sig["id"])
        except (StressError, MarketDataMissing) as e:
            log.info("rule %s matched signal %s but could not run: %s", r["id"], sig["id"], e)
            continue
        if source == "replay":
            _replay_cooldown[r["id"]] = now
        else:     # atomic claim: only one worker fires a rule inside its cooldown
            claimed = await pool.fetchval(
                "UPDATE stress_rules SET last_fired = $2 WHERE id = $1 AND (last_fired IS NULL OR last_fired <= $2::timestamptz - make_interval(mins => cooldown_minutes)) RETURNING id",
                r["id"], now)
            if not claimed:
                continue
        aid = f"al-{uuid.uuid4().hex[:12]}"
        title = f"Stress rule fired: {r['event_type']} (impact {sig['impact']:.1f})"
        async with pool.acquire() as con:
            async with con.transaction():
                await con.execute("INSERT INTO alerts (id, ts, severity, title, message, signal_id, source) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                                  aid, now, severity(res), title, res["narrative"], sig["id"], source)
                await ledger.append_con(con, "stress-rules", "rule_fired", f"Rule {r['id']} fired on signal {sig['id']}",
                                        {"ruleId": r["id"], "signalId": sig["id"], "runId": res["id"], "impact": sig["impact"],
                                         "integrity": sig["integrity"]["score"], "source": source}, ts=now)
        await publish(redis, "alert", {"id": aid, "ts": now.isoformat(), "severity": severity(res), "title": title,
                                       "message": res["narrative"], "signalId": sig["id"], "source": source}, source)
        fired.append(res)
    return fired


async def list_runs(pool, source: str = "live", limit: int = 30) -> list:
    rows = await pool.fetch("SELECT result FROM stress_runs WHERE source=$1 ORDER BY ts DESC LIMIT $2", source, limit)
    return [json.loads(r["result"]) if isinstance(r["result"], str) else r["result"] for r in rows]


async def get_run(pool, run_id: str):
    r = await pool.fetchval("SELECT result FROM stress_runs WHERE id = $1", run_id)
    if r is None:
        raise KeyError(run_id)
    return json.loads(r) if isinstance(r, str) else r
