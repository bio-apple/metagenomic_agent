"""Workflow snippet RAG (nf-core / Snakemake curated docs)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

SNIPPET_PATH = Path(__file__).resolve().parent / "workflow_snippets.json"


@lru_cache(maxsize=1)
def load_snippets() -> list[dict[str, Any]]:
    if SNIPPET_PATH.exists():
        return list(json.loads(SNIPPET_PATH.read_text(encoding="utf-8")).get("snippets") or [])
    return []


def retrieve_workflow_snippets(query: str, engine: str | None = None, top_k: int = 3) -> list[dict[str, Any]]:
    tokens = set(re.findall(r"[a-z0-9_\-]{3,}|[\u4e00-\u9fff]+", (query or "").lower()))
    scored = []
    for snip in load_snippets():
        if engine and snip.get("engine") != engine:
            continue
        blob = " ".join(
            [
                snip.get("id", ""),
                snip.get("title", ""),
                " ".join(snip.get("tags") or []),
                snip.get("body", "")[:500],
            ]
        ).lower()
        score = sum(1 for t in tokens if t in blob)
        if score:
            scored.append({**snip, "score": score})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k] or load_snippets()[:top_k]
