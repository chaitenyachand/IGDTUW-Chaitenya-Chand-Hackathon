from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ...audit import ledger
from .. import shape
from ..common import ApiError, ok

router = APIRouter()


@router.get("/api/audit")
async def audit(request: Request, limit: int = Query(50, ge=1, le=500), cursor: str | None = None,
                action: str | None = None, actor: str | None = None):
    """Newest first. `meta.nextCursor` is opaque: pass it back unchanged as ?cursor= for the next page; null on the last page."""
    try:
        before = int(cursor) if cursor else None
    except ValueError:
        raise ApiError(400, "bad_cursor", "invalid cursor")
    rows = await ledger.list_entries(request.app.state.pool, limit, before, action, actor)
    nxt = str(rows[-1]["seq"]) if len(rows) == limit else None
    return ok([shape.audit_entry(r) for r in rows], nextCursor=nxt)


@router.get("/api/audit/verify")
async def verify(request: Request):
    return ok(shape.audit_verify(await ledger.verify(request.app.state.pool)))
