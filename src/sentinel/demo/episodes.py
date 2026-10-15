"""Replay episodes: the manifest (data/replay/episodes.yaml) and the archived documents (data/replay/<id>.jsonl)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..ingest.base import Document

REPLAY_DIR = Path(os.environ.get("REPLAY_DIR", "data/replay"))


class EpisodeNotFound(KeyError):
    pass


class ReplayDataMissing(RuntimeError):
    """The episode exists in the manifest but its archived documents have not been downloaded."""


def _dt(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def manifest(directory: Path | None = None) -> list:
    f = (directory or REPLAY_DIR) / "episodes.yaml"
    if not f.exists():
        return []
    out = []
    for e in (yaml.safe_load(f.read_text()) or {}).get("episodes", []):
        out.append({"id": e["id"], "title": e["title"], "description": e.get("description", ""), "eventType": e.get("eventType"),
                    "start": _dt(e["start"]), "end": _dt(e["end"]), "keywords": list(e.get("keywords", []))})
    return out


def get_episode(episode_id: str, directory: Path | None = None) -> dict:
    ep = next((e for e in manifest(directory) if e["id"] == episode_id), None)
    if ep is None:
        raise EpisodeNotFound(episode_id)
    return ep


def episode_path(episode_id: str, directory: Path | None = None) -> Path:
    return (directory or REPLAY_DIR) / f"{episode_id}.jsonl"


def count_documents(episode_id: str, directory: Path | None = None) -> int:
    p = episode_path(episode_id, directory)
    if not p.exists():
        return 0
    with open(p) as fh:
        return sum(1 for line in fh if line.strip())


def list_episodes(directory: Path | None = None) -> list:
    out = []
    for e in manifest(directory):
        n = count_documents(e["id"], directory)
        out.append({"id": e["id"], "title": e["title"], "description": e["description"], "eventType": e["eventType"],
                    "start": e["start"].isoformat(), "end": e["end"].isoformat(), "documents": n,
                    "available": n > 0, "fetchCommand": f"make replay-fetch EPISODE={e['id']}"})
    return out


def record_to_document(rec: dict) -> Document:
    """One archived JSONL record -> a Document in replay mode, keeping its ORIGINAL publication time."""
    return Document(rec.get("sourceType", "news"), rec["source"], rec["key"], rec.get("url"), _dt(rec["publishedAt"]),
                    rec["title"], rec.get("text") or rec["title"], author=rec.get("author"), language=rec.get("language", "en"),
                    meta={**(rec.get("meta") or {}), "replayEpisode": rec.get("episode")}, mode="replay")


def load_documents(episode_id: str, limit: int | None = None, directory: Path | None = None) -> list:
    get_episode(episode_id, directory)
    p = episode_path(episode_id, directory)
    if not p.exists() or count_documents(episode_id, directory) == 0:
        raise ReplayDataMissing(f"no archived documents for '{episode_id}': run `make replay-fetch EPISODE={episode_id}`")
    docs = []
    with open(p) as fh:
        for line in fh:
            if line.strip():
                docs.append(record_to_document(json.loads(line)))
    docs.sort(key=lambda d: (d.published_at, d.key))
    return docs[:limit] if limit else docs
