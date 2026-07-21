"""Reporter Agent — diversity / pathway visualization narrative + biology interpretation.

Consumes statistics, function, literature, and visualization artifacts to write a
structured biological report section (Alpha/Beta, KEGG/COG/GO) before final HTML.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.domain_rag import retrieve_sops
from metagenomic_agent.knowledge.grounded_interp import write_grounded_interp
from metagenomic_agent.messaging import append_msg, emit


def _pathway_notes(artifacts: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    func = artifacts.get("functional") or artifacts.get("function") or {}
    # Per-sample or aggregate
    pathways: list[str] = []
    if isinstance(func, dict):
        for v in func.values() if any(isinstance(x, dict) for x in func.values()) else [func]:
            if not isinstance(v, dict):
                continue
            for key in ("top_pathways", "kegg", "cog", "go", "pathways"):
                val = v.get(key)
                if isinstance(val, list):
                    pathways.extend(str(x) for x in val[:8])
                elif isinstance(val, dict):
                    pathways.extend(list(val.keys())[:8])
    pathways = list(dict.fromkeys(pathways))[:12]
    if pathways:
        notes.append("Top functional signals (KEGG/COG/GO-style): " + ", ".join(pathways))
    else:
        notes.append(
            "Functional pathway table not populated in this run — "
            "enable HUMAnN3/eggNOG (pipeline.enable_functional) for KEGG/COG/GO summaries."
        )
    return notes


def _diversity_notes(artifacts: dict[str, Any], statistics: dict[str, Any] | None) -> list[str]:
    notes: list[str] = []
    stats = statistics or artifacts.get("statistics") or {}
    alpha = stats.get("alpha") or artifacts.get("diversity") or {}
    if isinstance(alpha, dict) and alpha:
        notes.append(f"Alpha diversity metrics available: {', '.join(list(alpha.keys())[:6])}")
    else:
        div_dir_hint = artifacts.get("diversity_analysis") or stats.get("outdir")
        notes.append(
            "Alpha/Beta diversity figures are produced by the visualization layer "
            f"(diversity_analysis={div_dir_hint or 'results/diversity_analysis'})."
        )
    n_bio = stats.get("n_biomarkers")
    if n_bio is not None:
        notes.append(f"Differential biomarkers detected: {n_bio}")
    return notes


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    arts = dict(state.get("artifacts") or {})
    query = state.get("user_query") or ""
    sops = retrieve_sops(query + " alpha beta kegg diversity", top_k=2)
    lit = arts.get("literature") or {}
    viz = arts.get("visualization") or {}
    critic = state.get("critic") or arts.get("critic") or {}
    planner = arts.get("planner") or {}

    diversity = _diversity_notes(arts, state.get("statistics"))
    pathways = _pathway_notes(arts)
    grounded = write_grounded_interp(state)

    interpretation = [
        f"Study framing (Planner): assay=`{planner.get('recommended_assay')}`, "
        f"env=`{planner.get('sample_environment')}`, goal=`{planner.get('study_goal')}`.",
        *diversity,
        *pathways,
        grounded.get("pcoa_note") or "",
        "### Table-bound differential claims (p / q / effect from program tables)",
        *(grounded.get("interpretation_bullets") or ["_(no biomarker table rows)_"]),
        "### Pathways (from functional tables only)",
        *(grounded.get("pathway_bullets") or ["_(no pathway rows)_"]),
    ]
    if critic and not critic.get("passed", True):
        interpretation.append(
            "QC & Critic raised warnings — interpret diversity/pathway claims cautiously: "
            + "; ".join((critic.get("warnings") or critic.get("all_warnings") or [])[:3])
        )
    if lit.get("n_papers") or lit.get("evidence_table") or arts.get("evidence_chain"):
        interpretation.append(
            "Literature/evidence chain attached; taxa stats remain table-bound (no invented p/effect)."
        )
    else:
        interpretation.append("Evidence chain sparse — avoid strong causal language in the narrative.")

    for sop in sops:
        interpretation.append(f"SOP `{sop.get('id')}`: {sop.get('title')}")

    report = {
        "role": "reporter",
        "title": "Biological interpretation (diversity & pathways)",
        "interpretation": [x for x in interpretation if x],
        "figures": {
            "interactive_dashboard": viz.get("dashboard") or str(Path(state["outdir"]) / "interactive_dashboard.html"),
            "diversity": "diversity_analysis/",
            "biomarkers": "biomarkers/",
        },
        "ontology_focus": ["Alpha/Beta diversity", "KEGG", "COG", "GO"],
        "sops": [{"id": s.get("id"), "title": s.get("title")} for s in sops],
        "grounded_interp": {
            "n_allowed": grounded.get("n_allowed"),
            "n_blocked": grounded.get("n_blocked"),
            "allowed_taxa": (grounded.get("universe") or {}).get("allowed_taxa"),
            "path": grounded.get("path"),
        },
        "policy": "table_bound_taxa_pvalues_effects_no_hallucination",
    }

    out = Path(state["outdir"]) / "reporter"
    out.mkdir(parents=True, exist_ok=True)
    (out / "biological_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Reporter — Biological Interpretation", ""]
    for line in interpretation:
        md.append(f"- {line}")
    md += [
        "",
        "## Ontologies",
        "- Alpha / Beta diversity",
        "- KEGG / COG / GO pathway summaries (when functional layer enabled)",
        "",
        "## Figures",
        f"- Dashboard: `{report['figures']['interactive_dashboard']}`",
        "",
    ]
    (out / "biological_report.md").write_text("\n".join(md), encoding="utf-8")

    amsg = emit("reporter", "report", "result", {"n_points": len(interpretation)})
    arts["reporter"] = {**report, "path": str(out / "biological_report.json")}
    return {
        "artifacts": arts,
        "messages": state.get("messages", []) + [f"Reporter wrote biological interpretation ({len(interpretation)} points)"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }
