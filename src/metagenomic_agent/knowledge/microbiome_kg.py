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
        if link.get("mechanism"):
            mech = f"mechanism:{link['mechanism']}"
            add_node(mech, "Function", name=link["mechanism"])
            edges.append({"source": mid, "target": mech, "relation": "mechanism"})

    # Drug resistance edges from CARD entries
    for e in (index.get("databases") or {}).get("card") or []:
        eid = f"card:{e.get('id') or e.get('name')}"
        add_node(eid, "Gene", name=e.get("name"), database="card", resistance=True)
        add_node("concept:drug_resistance", "Phenotype", name="drug_resistance")
        edges.append({"source": eid, "target": "concept:drug_resistance", "relation": "confers_resistance"})
        for hint in e.get("taxa_hint") or []:
            tid = f"taxon:{hint}"
            add_node(tid, "Microbe", name=hint)
            edges.append({"source": tid, "target": eid, "relation": "carries_arg"})

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


def opposing_evidence(taxon: str, disease: str | None = None) -> dict[str, Any]:
    """Find supporting vs conflicting disease associations for a microbe."""
    from metagenomic_agent.rag import load_index

    genus = taxon.split()[0].lower()
    disease_l = (disease or "").lower()
    support: list[dict[str, Any]] = []
    conflict: list[dict[str, Any]] = []
    effects: dict[str, list[dict[str, Any]]] = {}
    for link in load_index().get("evidence_links") or []:
        sp = str(link.get("species") or "").lower()
        if genus not in sp and genus not in str(link.get("species") or "").lower():
            continue
        if disease_l and disease_l not in str(link.get("disease") or "").lower():
            # still keep for conflict scan across diseases if disease filter empty
            if disease_l:
                continue
        effect = str(link.get("effect") or "").capitalize()
        effects.setdefault(effect, []).append(link)
        support.append(link)
    # Conflicts: both Up and Down for same disease, or curated contradiction flag
    if "Up" in effects and "Down" in effects:
        conflict = effects["Up"][:2] + effects["Down"][:2]
    for link in support:
        if link.get("contradicts") or str(link.get("note") or "").lower().startswith("conflict"):
            conflict.append(link)
    return {
        "taxon": taxon.split()[0],
        "disease": disease,
        "supporting": support[:6],
        "conflicts": conflict[:6],
        "confidence_hint": "low" if conflict else ("high" if support else "medium"),
    }


def subgraph_for_taxon(taxon: str) -> dict[str, Any]:
    """Extract a small Microbe–Disease–Gene–Pathway–Resistance subgraph."""
    kg = build_kg()
    genus = taxon.split()[0].lower()
    keep_nodes: set[str] = set()
    keep_edges: list[dict[str, Any]] = []
    for e in kg["edges"]:
        src, tgt = str(e.get("source", "")), str(e.get("target", ""))
        if genus in src.lower() or genus in tgt.lower():
            keep_edges.append(e)
            keep_nodes.add(src)
            keep_nodes.add(tgt)
    nodes = [n for n in kg["nodes"] if n["id"] in keep_nodes]
    return {"taxon": taxon.split()[0], "nodes": nodes, "edges": keep_edges, "n_nodes": len(nodes), "n_edges": len(keep_edges)}
