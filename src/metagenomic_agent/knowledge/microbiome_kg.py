"""Microbiome Knowledge Graph — Microbe↔Gene↔Pathway↔Disease↔Publication."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from metagenomic_agent.rag import load_index, retrieve_multi

KG_CACHE = Path(__file__).resolve().parent / "microbiome_kg.json"


@lru_cache(maxsize=1)
def build_kg() -> dict[str, Any]:
    """Build a compact KG from curated bio index + evidence links."""
    index = load_index()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(nid: str, ntype: str, **props: Any) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, **props}

    for db, entries in (index.get("databases") or {}).items():
        ntype = {
            "gtdb": "Microbe",
            "ncbi_taxonomy": "Microbe",
            "kegg": "Pathway",
            "uniprot": "Protein",
            "eggnog": "Gene",
            "card": "Gene",
            "vfdb": "Gene",
            "mgnify": "Microbe",
        }.get(db, "Entity")
        for e in entries or []:
            eid = f"{db}:{e.get('id') or e.get('name')}"
            add_node(eid, ntype, name=e.get("name"), database=db, notes=e.get("notes"))
            for alias in e.get("aliases") or []:
                add_node(f"alias:{alias}", "Alias", name=alias)
                edges.append({"source": eid, "target": f"alias:{alias}", "relation": "aka"})
            for hint in e.get("taxa_hint") or []:
                tid = f"taxon:{hint}"
                add_node(tid, "Microbe", name=hint)
                edges.append({"source": eid, "target": tid, "relation": "associated_taxon"})
            if e.get("pathway"):
                pid = f"pathway:{e['pathway']}"
                add_node(pid, "Pathway", name=e["pathway"])
                edges.append({"source": eid, "target": pid, "relation": "in_pathway"})

    for link in index.get("evidence_links") or []:
        sp = str(link.get("species") or "unknown")
        mid = f"taxon:{sp.split()[0]}"
        did = f"disease:{link.get('disease') or 'unspecified'}"
        pub = f"pmid:{link.get('pmid') or 'na'}"
        add_node(mid, "Microbe", name=sp.split()[0])
        add_node(did, "Disease", name=link.get("disease"))
        add_node(pub, "Publication", pmid=link.get("pmid"), effect=link.get("effect"))
        edges.append({"source": mid, "target": did, "relation": "associated_with", "effect": link.get("effect")})
        edges.append({"source": mid, "target": pub, "relation": "supported_by"})
        edges.append({"source": pub, "target": did, "relation": "studies"})

    return {"nodes": list(nodes.values()), "edges": edges, "n_nodes": len(nodes), "n_edges": len(edges)}


def write_kg(outdir: Path) -> dict[str, Any]:
    kg = build_kg()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "microbiome_kg.json"
    path.write_text(json.dumps(kg, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [
        "# Microbiome Knowledge Graph",
        "",
        f"- nodes: {kg['n_nodes']}",
        f"- edges: {kg['n_edges']}",
        "",
        "Types: Microbe · Gene · Protein · Pathway · Disease · Publication",
        "",
    ]
    (outdir / "microbiome_kg.md").write_text("\n".join(md), encoding="utf-8")
    return {**kg, "path": str(path)}


def explain_microbe(taxon: str, top_k: int = 8) -> dict[str, Any]:
    """Traverse KG + RAG for grounded mechanism notes."""
    kg = build_kg()
    genus = taxon.split()[0]
    related = []
    for e in kg["edges"]:
        if genus.lower() in str(e.get("source", "")).lower() or genus.lower() in str(e.get("target", "")).lower():
            related.append(e)
    multi = retrieve_multi(genus, dbs=["gtdb", "kegg", "card", "vfdb", "uniprot"], top_k_per_db=2, mode="hybrid")
    return {
        "taxon": genus,
        "kg_edges": related[:top_k],
        "rag": multi,
        "chain_hint": f"{genus} → pathways/ARG/VF → disease associations (KG+RAG grounded)",
    }
