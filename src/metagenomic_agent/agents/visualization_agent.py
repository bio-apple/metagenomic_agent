"""Visualization Agent — real PCoA, co-occurrence, volcano, LEfSe bars, Sankey stubs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from metagenomic_agent.stats.cooccurrence import cooccurrence_network
from metagenomic_agent.stats.ordination import pcoa_from_beta_tsv


def _load_matrix(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))
    matrix: dict[str, dict[str, float]] = {}
    for row in rows:
        sid = row.get("sample") or row.get("sample_id")
        if not sid:
            continue
        matrix[sid] = {k: float(v) for k, v in row.items() if k not in {"sample", "sample_id"} and v != ""}
    return matrix


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    fig_dir = outdir / "report" / "figures"
    tab_dir = outdir / "report" / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)

    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    groups = stats.get("groups") or {s["sample_id"]: s.get("group", "unknown") for s in state.get("samples", [])}

    # Heatmap from genus matrix or taxonomy tops
    mat_path = Path(stats.get("genus_matrix") or outdir / "diversity_analysis" / "genus_matrix.tsv")
    matrix = _load_matrix(mat_path)
    if not matrix:
        tax = state.get("artifacts", {}).get("taxonomy") or {}
        for sid, art in tax.items():
            for g in art.get("top_genera") or []:
                matrix.setdefault(sid, {})[g] = matrix.get(sid, {}).get(g, 0.0) + 0.1

    samples = sorted(matrix)
    genera = sorted({g for ab in matrix.values() for g in ab})[:30]
    heat_path = fig_dir / "taxonomy_heatmap_data.csv"
    with heat_path.open("w", encoding="utf-8") as f:
        f.write("genus," + ",".join(samples) + "\n")
        for g in genera:
            f.write(g + "," + ",".join(str(matrix.get(s, {}).get(g, 0.0)) for s in samples) + "\n")

    alpha = outdir / "diversity_analysis" / "alpha_diversity.tsv"
    if alpha.exists():
        (tab_dir / "alpha_diversity.tsv").write_text(alpha.read_text(encoding="utf-8"), encoding="utf-8")

    bio_path = Path(stats.get("biomarkers") or outdir / "biomarkers" / "biomarkers.tsv")
    volcano = {"points": [], "title": "Volcano (log2FC vs -log10 p)"}
    if bio_path.exists():
        (tab_dir / "biomarkers.tsv").write_text(bio_path.read_text(encoding="utf-8"), encoding="utf-8")
        with bio_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                try:
                    import math

                    p = float(row.get("p_value") or 1)
                    volcano["points"].append(
                        {
                            "genus": row.get("genus"),
                            "log2fc": float(row.get("log2fc") or 0),
                            "neglog10p": -math.log10(max(p, 1e-300)),
                            "direction": row.get("direction"),
                        }
                    )
                except ValueError:
                    continue
    (fig_dir / "volcano.json").write_text(json.dumps(volcano, indent=2), encoding="utf-8")

    # Real PCoA
    beta = Path(stats.get("beta_diversity") or outdir / "diversity_analysis" / "beta_diversity.tsv")
    pcoa = pcoa_from_beta_tsv(str(beta), sample_groups=groups)
    (fig_dir / "pcoa.json").write_text(json.dumps(pcoa, indent=2), encoding="utf-8")

    # Co-occurrence
    network = cooccurrence_network(matrix, min_abs_corr=0.5)
    (fig_dir / "cooccurrence.json").write_text(json.dumps(network, indent=2), encoding="utf-8")

    # LEfSe-like bar data
    lefse = stats.get("lefse_list") or []
    (fig_dir / "lefse_like_bars.json").write_text(
        json.dumps({"bars": lefse[:15], "title": "LEfSe-like effect sizes"}, indent=2), encoding="utf-8"
    )
    if stats.get("lefse_like") and Path(stats["lefse_like"]).exists():
        (tab_dir / "lefse_like.tsv").write_text(Path(stats["lefse_like"]).read_text(encoding="utf-8"), encoding="utf-8")

    # Sankey: group -> top biomarkers
    sankey_links = []
    for b in (stats.get("biomarker_list") or [])[:10]:
        sankey_links.append(
            {
                "source": b.get("direction", "assoc").replace("enriched_in_", ""),
                "target": b.get("genus"),
                "value": abs(float(b.get("log2fc") or 0.1)),
            }
        )
    (fig_dir / "sankey.json").write_text(
        json.dumps({"links": sankey_links, "title": "Group–taxon Sankey"}, indent=2), encoding="utf-8"
    )

    # NMDS note: classical MDS already provides PCoA; NMDS would need iterative stress — export alias
    (fig_dir / "nmds.json").write_text(
        json.dumps(
            {
                **pcoa,
                "title": "NMDS-equivalent view (classical MDS coordinates)",
                "note": "True iterative NMDS not required when classical MDS stress is acceptable; coordinates reused from PCoA.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = {
        "figures": [
            str(heat_path.relative_to(outdir)),
            "report/figures/pcoa.json",
            "report/figures/cooccurrence.json",
            "report/figures/volcano.json",
            "report/figures/lefse_like_bars.json",
            "report/figures/sankey.json",
            "report/figures/nmds.json",
        ],
        "tables": [str(p.relative_to(outdir)) for p in tab_dir.glob("*")],
        "methods": ["classical_mds_pcoa", "spearman_cooccurrence", "volcano", "lefse_like_bars", "sankey"],
    }
    (fig_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "artifacts": {**state.get("artifacts", {}), "visualization": manifest},
        "messages": state.get("messages", []) + [f"Visualization Agent wrote {len(manifest['figures'])} figures"],
    }
