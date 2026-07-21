"""Lightweight TF-IDF semantic retrieval over curated bio indices (no heavy deps)."""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Any

from metagenomic_agent.rag import load_index


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_\-]{2,}|[\u4e00-\u9fff]+", (text or "").lower())


def _doc_text(entry: dict[str, Any], db: str) -> str:
    parts = [
        db,
        str(entry.get("id", "")),
        str(entry.get("name", "")),
        str(entry.get("notes", "")),
        str(entry.get("pathway", "")),
        str(entry.get("family", "")),
        str(entry.get("category", "")),
        str(entry.get("biome", "")),
        str(entry.get("lineage", "")),
        " ".join(entry.get("aliases") or []),
        " ".join(entry.get("taxa_hint") or []),
    ]
    return " ".join(parts)


@lru_cache(maxsize=1)
def _build_corpus() -> tuple[list[dict[str, Any]], list[Counter], dict[str, float]]:
    index = load_index()
    docs: list[dict[str, Any]] = []
    tfs: list[Counter] = []
    df: Counter = Counter()
    for db, entries in (index.get("databases") or {}).items():
        for e in entries:
            docs.append({"database": db, **e})
            toks = _tokenize(_doc_text(e, db))
            tf = Counter(toks)
            tfs.append(tf)
            for t in tf:
                df[t] += 1
    n = max(len(docs), 1)
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    return docs, tfs, idf


def _tfidf_vec(tf: Counter, idf: dict[str, float]) -> dict[str, float]:
    return {t: (c / max(sum(tf.values()), 1)) * idf.get(t, 0.0) for t, c in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    num = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    da = math.sqrt(sum(v * v for v in a.values())) or 1.0
    db = math.sqrt(sum(v * v for v in b.values())) or 1.0
    return num / (da * db)


def semantic_retrieve(query: str, top_k: int = 5, db: str | None = None) -> list[dict[str, Any]]:
    docs, tfs, idf = _build_corpus()
    qv = _tfidf_vec(Counter(_tokenize(query)), idf)
    scored = []
    for doc, tf in zip(docs, tfs):
        if db and doc.get("database") != db:
            continue
        score = _cosine(qv, _tfidf_vec(tf, idf))
        if score > 0:
            scored.append({**doc, "score": round(score, 4), "retrieval": "tfidf"})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]
