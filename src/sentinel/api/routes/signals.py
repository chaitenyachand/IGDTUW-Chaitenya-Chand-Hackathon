from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ...signals_io import row_to_api
from ..common import ApiError, decode_cursor, encode_cursor, ok

router = APIRouter()


@router.get("/api/documents")
async def documents(request: Request, limit: int = Query(50, le=200), sourceType: str | None = None):
    q = ("SELECT id, source_type, source_name, url, published_at, title, dup_of FROM documents "
         "WHERE ($1::text IS NULL OR source_type = $1) ORDER BY published_at DESC LIMIT $2")
    rows = await request.app.state.pool.fetch(q, sourceType, limit)
    return ok([{"id": r["id"], "sourceType": r["source_type"], "sourceName": r["source_name"], "url": r["url"],
                "publishedAt": r["published_at"].isoformat(), "title": r["title"], "dupOf": r["dup_of"]} for r in rows])


@router.get("/api/signals")
async def signals(request: Request, limit: int = Query(50, ge=1, le=200), cursor: str | None = None, entity: str | None = None,
                  eventType: str | None = None, minImpact: float | None = None, sourceType: str | None = None,
                  mode: str | None = None):
    where, args = [], []

    def add(cond: str, value):
        args.append(value)
        where.append(cond.replace("?", f"${len(args)}"))

    if entity:
        add("(lower(entity) = lower(?) OR upper(ticker) = upper(?))", entity)
    if eventType:
        add("event_type = ?", eventType)
    if minImpact is not None:
        add("impact >= ?", minImpact)
    if sourceType:
        add("source_type = ?", sourceType)
    if mode:
        add("mode = ?", mode)
    else:
        where.append("mode <> 'replay'")             # replayed episodes are shown only when asked for (mode=replay)
    if cursor:
        try:
            ts, sid = decode_cursor(cursor)
        except ValueError:
            raise ApiError(400, "bad_cursor", "invalid cursor")
        args.extend([ts, sid])
        where.append(f"(ts, id) < (${len(args) - 1}, ${len(args)})")
    args.append(limit + 1)
    sql = ("SELECT * FROM signals" + (" WHERE " + " AND ".join(where) if where else "") +
           f" ORDER BY ts DESC, id DESC LIMIT ${len(args)}")
    rows = await request.app.state.pool.fetch(sql, *args)
    page = rows[:limit]
    nxt = encode_cursor(page[-1]["ts"], page[-1]["id"]) if len(rows) > limit else None
    modes = {r["mode"] for r in page}
    return ok([row_to_api(r) for r in page], source=modes.pop() if len(modes) == 1 else "live", nextCursor=nxt)


@router.get("/api/signals/{signal_id}")
async def signal_detail(request: Request, signal_id: str):
    r = await request.app.state.pool.fetchrow("SELECT * FROM signals WHERE id = $1", signal_id)
    if not r:
        raise ApiError(404, "not_found", "signal not found")
    return ok(row_to_api(r), source=r["mode"])
