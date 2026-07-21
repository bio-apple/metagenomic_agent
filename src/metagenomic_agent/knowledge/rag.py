"""Biology RAG: Gut Microbe KB + optional PubMed enrichment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

KB_PATH = Path(__file__).resolve().parent / "gut_microbe_kb.json"


def load_kb() -> dict[str, Any]:
    if KB_PATH.exists():
        return json.loads(KB_PATH.read_text(encoding="utf-8"))
    return {"taxa": {}}


def retrieve(taxon: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Simple keyword RAG over the local gut microbe knowledge base."""
    kb = load_kb()
    taxa = kb.get("taxa", {})
    key = taxon.strip()
    hits: list[dict[str, Any]] = []
    if key in taxa:
        hits.append({"taxon": key, **taxa[key], "score": 1.0})
    # fuzzy: genus-level match
    genus = key.split()[0] if key else ""
    for name, entry in taxa.items():
        if name == key:
            continue
        if genus and (name.startswith(genus) or genus in name):
            hits.append({"taxon": name, **entry, "score": 0.7})
    hits.sort(key=lambda x: -x.get("score", 0))
    return hits[:top_k]


def explain_biomarkers(genera: list[str], query: str = "") -> dict[str, Any]:
    explanations = []
    for g in genera:
        docs = retrieve(g)
        if docs:
            d = docs[0]
            explanations.append(
                {
                    "taxon": g,
                    "mechanism": d.get("mechanism", ""),
                    "phenotype": d.get("phenotype", ""),
                    "references": d.get("references", []),
                    "source": "gut_microbe_kb",
                }
            )
        else:
            explanations.append(
                {
                    "taxon": g,
                    "mechanism": f"{g} appears in human microbiome studies related to: {query or 'gut ecology'}.",
                    "phenotype": "",
                    "references": [],
                    "source": "fallback",
                }
            )
    return {"explanations": explanations, "kb": str(KB_PATH)}


def search_kb(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    kb = load_kb()
    tokens = set(re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fff]+", query.lower()))
    scored = []
    for name, entry in kb.get("taxa", {}).items():
        blob = f"{name} {entry.get('mechanism', '')} {entry.get('phenotype', '')}".lower()
        score = sum(1 for t in tokens if t in blob)
        if score:
            scored.append({"taxon": name, **entry, "score": score})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]
