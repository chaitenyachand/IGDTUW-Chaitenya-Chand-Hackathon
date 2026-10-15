"""Append-only, hash-chained audit ledger.

hash_n = SHA256(prev_hash + canonical_json(entry_n)). The table has a trigger that rejects UPDATE and DELETE, so the
only way to alter history is to bypass the database, and `verify` then reports the first entry where the chain breaks.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone

LOCK_KEY = 724_001            # advisory lock so concurrent writers append to one linear chain


def _norm(o):
    """Canonical form that survives a JSONB round trip (integral floats become ints; NaN/inf become null)."""
    if isinstance(o, dict):
        return {str(k): _norm(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_norm(v) for v in (sorted(o, key=str) if isinstance(o, set) else o)]
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return o
    if isinstance(o, int):
        return o
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            return None
        return int(o) if o.is_integer() else o
    if isinstance(o, datetime):
        return o.astimezone(timezone.utc).isoformat()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def canonical_json(obj) -> str:
    return json.dumps(_norm(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(prev_hash, entry: dict) -> str:
    return hashlib.sha256(((prev_hash or "") + canonical_json(entry)).encode("utf-8")).hexdigest()


def _entry(id_: str, ts: datetime, actor: str, action: str, summary: str, payload) -> dict:
    return {"id": id_, "ts": ts.astimezone(timezone.utc).isoformat(), "actor": actor, "action": action,
            "summary": summary, "payload": payload}


async def append_con(con, actor: str, action: str, summary: str, payload=None, ts: datetime | None = None) -> dict:
    """Append inside an open transaction on `con`."""
    payload = json.loads(canonical_json(payload if payload is not None else {}))
    ts = (ts or datetime.now(timezone.utc)).astimezone(timezone.utc)
    id_ = "aud-" + uuid.uuid4().hex[:16]
    await con.execute("SELECT pg_advisory_xact_lock($1)", LOCK_KEY)
    prev = await con.fetchval("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1")
    e = _entry(id_, ts, actor, action, summary, payload)
    h = entry_hash(prev, e)
    seq = await con.fetchval(
        "INSERT INTO audit_log (id, ts, actor, action, summary, payload, hash, prev_hash) "
        "VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8) RETURNING seq", id_, ts, actor, action, summary, json.dumps(payload), h, prev)
    return {"seq": seq, **e, "hash": h, "prevHash": prev}


async def append(pool, actor: str, action: str, summary: str, payload=None, ts: datetime | None = None) -> dict:
    async with pool.acquire() as con:
        async with con.transaction():
            return await append_con(con, actor, action, summary, payload, ts)


def _row_entry(r) -> dict:
    p = r["payload"]
    return _entry(r["id"], r["ts"], r["actor"], r["action"], r["summary"], json.loads(p) if isinstance(p, str) else p)


async def verify(pool, batch: int = 2000) -> dict:
    """Recompute the whole chain. Returns the first broken entry, if any."""
    prev, n, last_seq = None, 0, 0
    while True:
        rows = await pool.fetch("SELECT * FROM audit_log WHERE seq > $1 ORDER BY seq LIMIT $2", last_seq, batch)
        if not rows:
            break
        for r in rows:
            n += 1
            last_seq = r["seq"]
            if (r["prev_hash"] or None) != prev:
                return {"ok": False, "entries": n, "headHash": prev,
                        "firstBroken": {"seq": r["seq"], "id": r["id"], "reason": "prev_hash does not match the previous entry"}}
            if entry_hash(prev, _row_entry(r)) != r["hash"]:
                return {"ok": False, "entries": n, "headHash": prev,
                        "firstBroken": {"seq": r["seq"], "id": r["id"], "reason": "entry content does not match its hash"}}
            prev = r["hash"]
    return {"ok": True, "entries": n, "headHash": prev, "firstBroken": None}


def row_to_api(r) -> dict:
    p = r["payload"]
    return {"seq": r["seq"], "id": r["id"], "ts": r["ts"].isoformat(), "actor": r["actor"], "action": r["action"],
            "summary": r["summary"], "payload": json.loads(p) if isinstance(p, str) else p, "hash": r["hash"],
            "prevHash": r["prev_hash"]}


async def list_entries(pool, limit: int = 50, before_seq: int | None = None, action: str | None = None,
                       actor: str | None = None) -> list:
    rows = await pool.fetch(
        "SELECT * FROM audit_log WHERE ($1::bigint IS NULL OR seq < $1) AND ($2::text IS NULL OR action = $2) "
        "AND ($3::text IS NULL OR actor = $3) ORDER BY seq DESC LIMIT $4", before_seq, action, actor, limit)
    return [row_to_api(r) for r in rows]
