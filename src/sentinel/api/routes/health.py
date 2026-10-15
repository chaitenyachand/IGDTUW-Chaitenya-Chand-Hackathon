from __future__ import annotations

from fastapi import APIRouter, Request

from ...demo import replay as demo_replay
from ..common import ok

router = APIRouter()


@router.get("/api/health")
async def health(request: Request):
    pool = request.app.state.pool
    sources = await pool.fetch(
        "SELECT source_name, enabled, status, last_success, last_error_msg, items_last_run, items_total, error_count "
        "FROM source_health ORDER BY source_name")
    stats = await pool.fetchrow(
        "SELECT count(*) AS total, count(*) FILTER (WHERE ingested_at > now() - interval '1 hour') AS last_hour, "
        "max(published_at) AS latest FROM documents WHERE mode <> 'replay'")
    sig = await pool.fetchrow("SELECT count(*) AS n, max(ts) AS latest, max(model_version) AS version FROM signals WHERE mode <> 'replay'")
    extra = await pool.fetchrow("SELECT (SELECT count(*) FROM event_library) AS lib, (SELECT count(*) FROM portfolio_holdings) AS hold, "
                                "(SELECT count(*) FROM stress_rules WHERE enabled) AS rules")
    return ok({
        "status": "ok",
        "documents": {"total": stats["total"], "lastHour": stats["last_hour"],
                      "latestPublishedAt": stats["latest"].isoformat() if stats["latest"] else None},
        "signals": {"total": sig["n"], "latestTs": sig["latest"].isoformat() if sig["latest"] else None},
        "modelVersion": sig["version"],
        "library": {"events": extra["lib"]}, "portfolio": {"holdings": extra["hold"]}, "stress": {"enabledRules": extra["rules"]},
        "replay": await demo_replay.status(pool),
        "sources": [{
            "name": r["source_name"], "enabled": r["enabled"], "status": r["status"],
            "lastSuccess": r["last_success"].isoformat() if r["last_success"] else None,
            "lastError": r["last_error_msg"], "itemsLastRun": r["items_last_run"],
            "itemsTotal": r["items_total"], "errorCount": r["error_count"]} for r in sources],
    })
