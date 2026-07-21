"""Evidence Integration Agent — merge stats + literature + KG into evidence pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.microbiome_kg import explain_microbe, write_kg
from metagenomic_agent.knowledge.reasoning_log import log_decision


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"]) / "evidence_integration"
    outdir.mkdir(parents=True, exist_ok=True)

    stats = state.get("statistics") or (state.get("artifacts") or {}).get("statistics") or {}
    lit = state.get("literature") or (state.get("artifacts") or {}).get("literature") or {}
    resistance = (state.get("artifacts") or {}).get("resistance") or {}
    biomarkers = list(stats.get("biomarker_list") or [])

    kg = write_kg(Path(state["outdir"]) / "knowledge_graph")
    integrated: list[dict[str, Any]] = []
    for b in biomarkers[:15]:
        genus = b.get("genus") or ""
        expl = explain_microbe(genus)
        lit_entry = next((e for e in (lit.get("entries") or []) if e.get("genus") == genus), None)
        integrated.append(
            {
                "genus": genus,
                "direction": b.get("direction"),
                "p_value": b.get("p_value"),
                "q_value": b.get("q_value"),
                "log2fc": b.get("log2fc"),
                "kg_chain": expl.get("chain_hint"),
                "kg_edges": (expl.get("kg_edges") or [])[:5],
                "literature": {
                    "interpretation": (lit_entry or {}).get("interpretation"),
                    "papers": ((lit_entry or {}).get("papers") or [])[:3],
                },
                "grounded": bool(lit_entry and lit_entry.get("grounded", True)),
            }
        )

    pack = {
        "role": "evidence_integration",
        "n_biomarkers": len(integrated),
        "items": integrated,
        "resistance_implications": (resistance.get("implications") or [])[:10],
        "kg_path": kg.get("path"),
        "kg_stats": {"n_nodes": kg.get("n_nodes"), "n_edges": kg.get("n_edges")},
    }
    (outdir / "evidence_pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [
        "# Evidence Integration",
        "",
        f"Integrated {len(integrated)} biomarker(s) with KG + literature.",
        f"KG: {kg.get('n_nodes')} nodes / {kg.get('n_edges')} edges.",
        "",
    ]
    for it in integrated:
        md.append(f"## {it['genus']}")
        md.append(f"- Stats: {it.get('direction')} p={it.get('p_value')} q={it.get('q_value')}")
        md.append(f"- KG: {it.get('kg_chain')}")
        md.append(f"- Lit: {(it.get('literature') or {}).get('interpretation') or 'n/a'}")
        md.append("")
    (outdir / "evidence_pack.md").write_text("\n".join(md), encoding="utf-8")

    reason = log_decision(
        state,
        "evidence",
        "Integrated biomarkers with KG and literature",
        f"n={len(integrated)}; kg_nodes={kg.get('n_nodes')}",
    )
    arts = {
        **(state.get("artifacts") or {}),
        **(reason.get("artifacts") or {}),
        "evidence_integration": pack,
        "knowledge_graph": kg,
    }
    return {
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [f"Evidence Integration: {len(integrated)} items; KG nodes={kg.get('n_nodes')}"],
    }
