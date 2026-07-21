"""Authority-grounded RAG — claims must be backed by GTDB/NCBI/KEGG/UniProt/CARD hits."""

from __future__ import annotations

from typing import Any

from metagenomic_agent.rag import retrieve, retrieve_multi

AUTHORITY_DBS = ("gtdb", "ncbi_taxonomy", "kegg", "uniprot", "card", "vfdb", "eggnog")


def ground_taxon(name: str, top_k: int = 3) -> dict[str, Any]:
    """Resolve a taxon against authoritative taxonomy DBs. Ungrounded names are rejected."""
    query = (name or "").strip()
    if not query:
        return {"taxon": name, "grounded": False, "reason": "empty_name", "hits": []}

    gtdb = retrieve("gtdb", query, top_k=top_k)
    ncbi = retrieve("ncbi_taxonomy", query, top_k=top_k)
    hits = gtdb + ncbi
    grounded = bool(hits)
    best = hits[0] if hits else None
    return {
        "taxon": query,
        "grounded": grounded,
        "canonical_name": (best or {}).get("name") or query,
        "gtdb_id": next((h.get("id") for h in gtdb if h.get("id")), None),
        "ncbi_taxid": next((h.get("id") for h in ncbi if h.get("id")), None),
        "database_ids": [
            {"database": h.get("database"), "id": h.get("id"), "name": h.get("name")}
            for h in hits
            if h.get("id")
        ],
        "hits": hits[:top_k],
        "reason": None if grounded else "not_found_in_gtdb_or_ncbi_curated_index",
    }


def ground_feature(feature: str, dbs: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Ground functional/AMR features in KEGG/UniProt/CARD/VFDB."""
    targets = dbs or ("kegg", "uniprot", "card", "vfdb", "eggnog")
    multi = retrieve_multi(feature, dbs=list(targets), top_k_per_db=2)
    flat = [h for hits in multi.values() for h in hits]
    flat.sort(key=lambda x: -x.get("score", 0))
    return {
        "feature": feature,
        "grounded": bool(flat),
        "hits": flat[:5],
        "database_ids": [
            {"database": h.get("database"), "id": h.get("id"), "name": h.get("name")}
            for h in flat[:5]
            if h.get("id")
        ],
    }


def filter_ungrounded_taxa(names: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    grounded_rows: list[dict[str, Any]] = []
    rejected: list[str] = []
    for n in names:
        row = ground_taxon(n)
        if row["grounded"]:
            grounded_rows.append(row)
        else:
            rejected.append(n)
    return grounded_rows, rejected


def authority_context_block(taxon: str) -> str:
    """Compact retrieval context for LLM prompts — model may only paraphrase this."""
    g = ground_taxon(taxon)
    f = ground_feature(taxon)
    lines = [f"TAXON={g.get('canonical_name')} grounded={g['grounded']}"]
    for d in g.get("database_ids") or []:
        lines.append(f"- {d['database']}:{d['id']} ({d.get('name')})")
    for h in (g.get("hits") or [])[:2]:
        if h.get("notes"):
            lines.append(f"- note: {h['notes']}")
    for d in f.get("database_ids") or []:
        lines.append(f"- feature_db {d['database']}:{d['id']}")
    if not g["grounded"]:
        lines.append("WARNING: taxon not in authority index — do not invent species facts.")
    return "\n".join(lines)
