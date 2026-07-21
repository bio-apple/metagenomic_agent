"""Biological database RAG layer — curated indices + pluggable remote backends."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "curated_bio_index.json"

SUPPORTED_DBS = (
    "gtdb",
    "ncbi_taxonomy",
    "refseq",
    "kegg",
    "eggnog",
    "vfdb",
    "card",
    "bacdive",
    "hmp",
    "mgnify",
)


@lru_cache(maxsize=1)
def load_index() -> dict[str, Any]:
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {"databases": {}, "evidence_links": []}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _score_entry(query: str, entry: dict[str, Any]) -> float:
    q = _norm(query)
    if not q:
        return 0.0
    blob_parts = [
        str(entry.get("id", "")),
        str(entry.get("name", "")),
        str(entry.get("notes", "")),
        str(entry.get("pathway", "")),
        str(entry.get("family", "")),
        str(entry.get("category", "")),
        str(entry.get("biome", "")),
        " ".join(entry.get("aliases") or []),
        " ".join(entry.get("taxa_hint") or []),
        str(entry.get("lineage", "")),
    ]
    blob = _norm(" ".join(blob_parts))
    tokens = set(re.findall(r"[a-z0-9_\-]{3,}|[\u4e00-\u9fff]+", q))
    if not tokens:
        return 1.0 if q in blob else 0.0
    hits = sum(1 for t in tokens if t in blob)
    bonus = 0.5 if q in blob or any(_norm(a) == q for a in (entry.get("aliases") or [])) else 0.0
    if entry.get("name") and _norm(str(entry["name"])).startswith(q.split()[0]):
        bonus += 0.3
    return float(hits) + bonus


def retrieve(db: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve curated records from a named biological database."""
    db_key = db.lower().strip()
    if db_key == "refseq":
        # RefSeq stub mirrors NCBI taxonomy + GTDB species names until local BLAST DB is configured
        hits = retrieve("ncbi_taxonomy", query, top_k=top_k) + retrieve("gtdb", query, top_k=top_k)
        for h in hits:
            h["database"] = "refseq"
        return hits[:top_k]

    index = load_index()
    entries = list((index.get("databases") or {}).get(db_key) or [])
    scored: list[dict[str, Any]] = []
    for e in entries:
        score = _score_entry(query, e)
        if score > 0:
            scored.append({"database": db_key, "score": round(score, 3), **e})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]


def retrieve_multi(query: str, dbs: list[str] | None = None, top_k_per_db: int = 3) -> dict[str, list[dict[str, Any]]]:
    targets = dbs or ["gtdb", "kegg", "card", "vfdb", "mgnify", "eggnog"]
    return {db: retrieve(db, query, top_k=top_k_per_db) for db in targets}


def evidence_for_taxon(taxon: str, disease_hint: str = "") -> list[dict[str, Any]]:
    """Return curated evidence rows for Evidence Table construction."""
    index = load_index()
    genus = taxon.split()[0] if taxon else ""
    rows: list[dict[str, Any]] = []
    for link in index.get("evidence_links") or []:
        sp = str(link.get("species", ""))
        if genus and genus.lower() not in sp.lower() and taxon.lower() not in sp.lower():
            continue
        if disease_hint and disease_hint.lower() not in str(link.get("disease", "")).lower():
            # still keep if disease empty match soft
            if disease_hint.lower() not in {"ibd", "gut", "inflammation", "crohn", "colitis"}:
                if disease_hint.lower() not in sp.lower():
                    pass
        rows.append(
            {
                "species": sp,
                "disease": link.get("disease"),
                "pmid": link.get("pmid"),
                "effect": link.get("effect"),
                "source": link.get("source", "curated"),
                "confidence": link.get("confidence", 0.5),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{link.get('pmid')}/" if link.get("pmid") else "",
            }
        )
    return rows


def annotate_features(features: list[str], dbs: list[str] | None = None) -> list[dict[str, Any]]:
    """Annotate taxonomy/function feature IDs against bio DB RAG."""
    out: list[dict[str, Any]] = []
    for feat in features:
        multi = retrieve_multi(feat, dbs=dbs or ["gtdb", "kegg", "card", "vfdb", "eggnog"], top_k_per_db=2)
        flat = [h for hits in multi.values() for h in hits]
        flat.sort(key=lambda x: -x.get("score", 0))
        out.append({"feature": feat, "hits": flat[:5]})
    return out
