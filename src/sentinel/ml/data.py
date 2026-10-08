"""Load gold-labelled documents together with the rule pipeline's decisions."""
from __future__ import annotations

import json


def source_group(name: str) -> str:
    return name.split(":")[0]


def model_text(row: dict) -> str:
    """Text fed to the models: the cleaned headline plus a coarse source token."""
    return f"__src_{source_group(row['source_name'])} {row['title']}"


async def load_gold(pool, split: str = "dev") -> list:
    """split='dev' for development; 'test' is the random held-out set, used only for the final evaluation."""
    rows = await pool.fetch(
        """SELECT d.id, d.source_name, f.clean_title AS title, f.features,
                  f.relevant AS rule_relevant, f.relevance AS rule_score, f.weak_event AS rule_event,
                  g.relevant AS gold_relevant, g.event_type AS gold_event, g.sentiment AS gold_sentiment
           FROM gold_labels g
           JOIN documents d ON d.id = g.document_id
           JOIN doc_features f ON f.document_id = g.document_id
           WHERE g.split = $1
           ORDER BY d.id""", split)
    out = []
    for r in rows:
        d = dict(r)
        f = d["features"]
        d["features"] = json.loads(f) if isinstance(f, str) else (f or {})
        out.append(d)
    return out
