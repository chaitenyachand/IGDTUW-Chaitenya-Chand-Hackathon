"""WebSocket protocol (design 12.3): /ws/signals?since=<streamId>&minImpact=<n>&source=all|live|replay.
Server messages {type, id, source, data}; types: hello, signal, precedent_ready, risk_index, rebalance, stress_run, alert, ping."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...events import STREAM
from .. import shape

router = APIRouter()
log = logging.getLogger(__name__)
PING_SECONDS = 20


def wanted(msg_type: str, source: str, data: dict, min_impact: float | None, want_source: str) -> bool:
    if want_source != "all" and source != want_source:
        return False
    if min_impact is not None and msg_type == "signal":
        return data.get("impact") is not None and data["impact"] >= min_impact
    return True


async def _tail(redis) -> str:
    top = await redis.xrevrange(STREAM, count=1)
    return top[0][0] if top else "0-0"


@router.websocket("/ws/signals")
async def ws_signals(ws: WebSocket, since: str | None = None, minImpact: float | None = None, source: str = "all"):
    await ws.accept()
    redis = ws.app.state.redis
    last = since or await _tail(redis)          # a concrete id: "$" would skip whatever arrives between two reads
    try:
        await ws.send_json({"type": "hello", "id": last, "source": "live", "data": {"stream": STREAM, "pingSeconds": PING_SECONDS}})
        while True:
            resp = await redis.xread({STREAM: last}, count=100, block=PING_SECONDS * 1000)
            if not resp:
                await ws.send_json({"type": "ping", "id": last, "source": "live", "data": {}})
                continue
            for _, entries in resp:
                for entry_id, fields in entries:
                    last = entry_id
                    t, src = fields.get("type", "signal"), fields.get("source", "live")
                    data = json.loads(fields["payload"])
                    if wanted(t, src, data, minImpact, source):
                        out = await shape.ws_data(ws.app.state.pool, t, data, src)
                        if out is not None:
                            await ws.send_json({"type": t, "id": entry_id, "source": src, "data": out})
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        return
    except Exception:                      # redis hiccup: close so the terminal reconnects with ?since=<last id> and loses nothing
        log.exception("websocket feed failed")
        await ws.close(code=1011)
