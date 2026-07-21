"""Visualization Agent — paper-oriented figures and tables layout."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    fig_dir = outdir / "report" / "figures"
    tab_dir = outdir / "report" / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)

    # Taxonomy heatmap-like matrix (CSV for downstream plotting)
    tax = state.get("artifacts", {}).get("taxonomy") or {}
    genera: dict[str, dict[str, float]] = {}
    for sid, art in tax.items():
        for g in art.get("top_genera") or []:
            genera.setdefault(g, {})[sid] = genera.get(g, {}).get(sid, 0.0) + 0.1
    heat_path = fig_dir / "taxonomy_heatmap_data.csv"
    samples = sorted({s for d in genera.values() for s in d})
    with heat_path.open("w", encoding="utf-8") as f:
        f.write("genus," + ",".join(samples) + "\n")
        for g, d in sorted(genera.items()):
            f.write(g + "," + ",".join(str(d.get(s, 0.0)) for s in samples) + "\n")

    # Diversity table copy
    alpha = outdir / "diversity_analysis" / "alpha_diversity.tsv"
    if alpha.exists():
        (tab_dir / "alpha_diversity.tsv").write_text(alpha.read_text(encoding="utf-8"), encoding="utf-8")

    # Biomarker volcano-like table
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    bio_path = Path(stats.get("biomarkers") or outdir / "biomarkers" / "biomarkers.tsv")
    volcano_rows = []
    if bio_path.exists():
        for row in _read_tsv(bio_path):
            volcano_rows.append(row)
        (tab_dir / "biomarkers.tsv").write_text(bio_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Simple Plotly-ready JSON for PCoA placeholder (Bray-Curtis stub coordinates)
    pcoa = {
        "type": "scatter",
        "title": "PCoA (Bray-Curtis stub)",
        "points": [
            {"sample": sid, "PC1": i * 0.1, "PC2": (len(tax) - i) * 0.05, "group": "n/a"}
            for i, sid in enumerate(tax.keys())
        ],
        "note": "Coordinates are placeholders until full distance matrix ordination is enabled.",
    }
    (fig_dir / "pcoa_stub.json").write_text(json.dumps(pcoa, indent=2), encoding="utf-8")

    # Network co-occurrence stub from top genera
    edges = []
    gens = list(genera.keys())
    for i in range(len(gens) - 1):
        edges.append({"source": gens[i], "target": gens[i + 1], "weight": 0.5})
    (fig_dir / "cooccurrence_stub.json").write_text(
        json.dumps({"nodes": gens, "edges": edges}, indent=2), encoding="utf-8"
    )

    manifest = {
        "figures": [
            str(heat_path.relative_to(outdir)),
            str((fig_dir / "pcoa_stub.json").relative_to(outdir)),
            str((fig_dir / "cooccurrence_stub.json").relative_to(outdir)),
        ],
        "tables": [str(p.relative_to(outdir)) for p in tab_dir.glob("*")],
        "requested_but_deferred": ["NMDS", "LEfSe cladogram", "Sankey", "full PCA"],
        "n_volcano_rows": len(volcano_rows),
    }
    (fig_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "artifacts": {**state.get("artifacts", {}), "visualization": manifest},
        "messages": state.get("messages", []) + [f"Visualization Agent wrote {len(manifest['figures'])} figure artifacts"],
    }
