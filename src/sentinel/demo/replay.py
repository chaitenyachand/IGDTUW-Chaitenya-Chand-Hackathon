"""Demo Director: replay a real archived episode through the SAME pipeline as live data (design section 9).

inject  : archived documents -> `documents` (mode='replay', original publication times) -> NLP features. The serving worker
          then scores them oldest first, paced, exactly like live documents; Module A, Module B and the risk index run
          "as of" each signal's own time and write replay-tagged state (source='replay'), never touching live state.
reset   : removes every replay document, signal and replay-tagged state row (the audit ledger is append-only and keeps
          its entries, which carry source='replay').
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .. import store
from ..audit import ledger
from ..config import settings
from ..ingest.dedupe import NearDuplicateIndex
from ..nlp import worker as nlp_worker
from ..stress import service as stress_service
from .episodes import get_episode, load_documents

REPLAY_STATE_TABLES = ("rebalance_events", "alerts", "stress_runs", "index_weights", "risk_index_history")


async def reset(pool, actor: str = "api") -> dict:
    async with pool.acquire() as con:
        async with con.transaction():
            docs = await con.fetchval("WITH d AS (DELETE FROM documents WHERE mode = 'replay' RETURNING 1) SELECT count(*) FROM d")
            state = {}
            for t in REPLAY_STATE_TABLES:
                state[t] = await con.fetchval(f"WITH d AS (DELETE FROM {t} WHERE source = 'replay' RETURNING 1) SELECT count(*) FROM d")
            await ledger.append_con(con, actor, "demo_reset", f"Replay state cleared ({docs} documents)", {"documents": docs, "state": state})
    stress_service._replay_cooldown.clear()
    return {"documentsRemoved": docs, "stateRemoved": state}


async def inject(pool, redis, episode_id: str, pace_seconds: float | None = None, limit: int | None = None,
                 clean: bool = True, actor: str = "api", directory=None) -> dict:
    ep = get_episode(episode_id, directory)
    docs = load_documents(episode_id, limit, directory)        # raises ReplayDataMissing when the archive is not downloaded
    cleared = await reset(pool, actor) if clean else None
    inserted = await store.insert_documents(pool, docs, NearDuplicateIndex())
    ids = [d.id for d, _ in inserted]
    rows = await pool.fetch("SELECT id, source_type, source_name, url, title, text, meta FROM documents WHERE id = ANY($1)", ids)
    await nlp_worker.process_rows(pool, None, rows)            # identical feature code as live documents
    pace = settings.replay_pace_seconds if pace_seconds is None else float(pace_seconds)
    await store.set_config(pool, "replay", {"episode": episode_id, "paceSeconds": pace,
                                            "startedAt": datetime.now(timezone.utc).isoformat(), "documents": len(ids)})
    await ledger.append(pool, actor, "demo_inject", f"Replay of '{ep['title']}' queued: {len(ids)} archived documents",
                        {"episode": episode_id, "documents": len(ids), "duplicates": sum(1 for _, d in inserted if d),
                         "window": [ep["start"].isoformat(), ep["end"].isoformat()], "paceSeconds": pace, "source": "replay"})
    return {"episode": episode_id, "title": ep["title"], "queued": len(ids), "duplicatesFlagged": sum(1 for _, d in inserted if d),
            "from": min((d.published_at for d, _ in inserted), default=ep["start"]).isoformat(),
            "to": max((d.published_at for d, _ in inserted), default=ep["end"]).isoformat(), "paceSeconds": pace,
            "cleared": cleared, "source": "replay"}


async def status(pool) -> dict:
    cfg = await store.get_config(pool, "replay") or {}
    r = await pool.fetchrow(
        "SELECT count(*) AS docs, count(f.document_id) AS featured, count(s.document_id) AS scored, "
        "count(*) FILTER (WHERE d.dup_of IS NOT NULL) AS dups, "
        "(SELECT count(*) FROM signals WHERE mode = 'replay') AS signals, "
        "(SELECT max(ts) FROM signals WHERE mode = 'replay') AS latest "
        "FROM documents d LEFT JOIN doc_features f ON f.document_id = d.id LEFT JOIN doc_scores s ON s.document_id = d.id "
        "WHERE d.mode = 'replay'")
    pending = r["docs"] - r["dups"] - r["scored"]
    return {"episode": cfg.get("episode"), "paceSeconds": cfg.get("paceSeconds"), "documents": r["docs"], "scored": r["scored"],
            "duplicates": r["dups"], "signals": r["signals"], "pending": max(pending, 0),
            "done": bool(r["docs"]) and pending <= 0, "latestSignalTs": r["latest"].isoformat() if r["latest"] else None}
