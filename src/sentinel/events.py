"""Real-time event fan-out. One Redis stream carries every WebSocket message type, so a reconnecting client can replay
what it missed with a single `since` id. Types: signal, precedent_ready, risk_index, rebalance, stress_run, alert."""
from __future__ import annotations

import json

STREAM = "stream:signals"
TYPES = {"signal", "precedent_ready", "risk_index", "rebalance", "stress_run", "alert"}


async def publish(redis, type_: str, data, source: str = "live"):
    """Append one message to the stream. Returns the Redis stream id (None when no Redis is configured)."""
    if redis is None:
        return None
    assert type_ in TYPES, type_
    return await redis.xadd(STREAM, {"type": type_, "source": source, "payload": json.dumps(data, default=str)},
                            maxlen=20000, approximate=True)


async def publish_many(redis, items: list):
    """Append several messages in one round trip. `items`: [(type, data, source)]. Returns the stream ids in order."""
    if redis is None or not items:
        return []
    pipe = redis.pipeline()
    for type_, data, source in items:
        assert type_ in TYPES, type_
        pipe.xadd(STREAM, {"type": type_, "source": source, "payload": json.dumps(data, default=str)},
                  maxlen=20000, approximate=True)
    return await pipe.execute()
