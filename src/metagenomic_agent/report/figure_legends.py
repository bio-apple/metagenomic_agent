"""Publication-style figure legends from visualization / statistics artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_legends(state: dict[str, Any]) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    viz_dir = outdir / "visualization"
    viz_dir.mkdir(parents=True, exist_ok=True)
    stats = state.get("statistics") or (state.get("artifacts") or {}).get("statistics") or {}
    viz = (state.get("artifacts") or {}).get("visualization") or {}
    query = state.get("user_query") or "metagenomic cohort"
    n_samples = len(state.get("samples") or [])
    n_bio = int(stats.get("n_biomarkers") or len(stats.get("biomarker_list") or []) or 0)
    q = ((state.get("config") or {}).get("visualization") or {}).get("default_q", 0.1)

    legends = [
        {
            "figure": 1,
            "title": "Alpha diversity",
            "legend": (
                f"Figure 1. Alpha-diversity distributions across samples (n={n_samples}) "
                f"for the study question: “{query}”. Metrics (e.g. Shannon/Simpson/observed richness) "
                "were computed from relative-abundance profiles after prevalence filtering. "
                "Boxes show interquartile range; whiskers extend to 1.5×IQR when boxplots are used."
            ),
        },
        {
            "figure": 2,
            "title": "Beta diversity / PCoA",
            "legend": (
                "Figure 2. Principal coordinate analysis (PCoA) based on Bray–Curtis dissimilarities "
                "of taxonomic profiles. Points represent samples; ellipses (if shown) indicate group "
                "dispersion. Axis labels report the percentage of variance explained by each coordinate."
            ),
        },
        {
            "figure": 3,
            "title": "Differential abundance",
            "legend": (
                f"Figure 3. Differential taxa highlighted at FDR q ≤ {q} "
                f"({n_bio} biomarker(s) detected in this run). Effect sizes and p/q values are taken "
                "from the statistics tables (Mann–Whitney U + BH-FDR and/or LEfSe-/ANCOM-like modules); "
                "ungrounded taxa are excluded from interpretation."
            ),
        },
        {
            "figure": 4,
            "title": "Taxonomic composition",
            "legend": (
                "Figure 4. Relative abundance of dominant genera (top-N by mean abundance). "
                "Stacked bars or heatmaps summarize community composition per sample or group. "
                "Low-prevalence features may have been removed per HITL OTU/ASV filter settings."
            ),
        },
    ]

    md = ["# Figure legends", ""]
    for L in legends:
        md.append(f"## Figure {L['figure']}. {L['title']}")
        md.append("")
        md.append(L["legend"])
        md.append("")

    md_path = viz_dir / "figure_legends.md"
    json_path = viz_dir / "figure_legends.json"
    md_path.write_text("\n".join(md), encoding="utf-8")
    json_path.write_text(json.dumps(legends, indent=2, ensure_ascii=False), encoding="utf-8")
    # Also under report/manuscript for writing
    ms = outdir / "report" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "figure_legends.md").write_text("\n".join(md), encoding="utf-8")

    return {
        "legends": legends,
        "path": str(md_path),
        "json_path": str(json_path),
        "viz_paths": viz,
    }
