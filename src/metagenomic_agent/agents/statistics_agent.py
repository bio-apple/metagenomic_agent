"""Statistics Agent — diversity, differential abundance, biomarkers."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_genus_matrix(taxonomy_profile: str | None, artifacts: dict[str, Any]) -> dict[str, dict[str, float]]:
    """sample -> genus -> abundance"""
    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    path = taxonomy_profile or artifacts.get("taxonomy_profile")
    if path and Path(path).exists():
        for line in Path(path).read_text().splitlines()[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                sample, genus, abund = parts[0], parts[1], float(parts[2])
                # prefer first tool occurrence
                matrix[sample].setdefault(genus, abund)
        return matrix

    for sid, art in artifacts.get("taxonomy", {}).items():
        for path_key in ("kraken2_abundance", "metaphlan_abundance"):
            p = art.get(path_key)
            if not p or not Path(p).exists():
                continue
            for line in Path(p).read_text().splitlines()[1:]:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    matrix[sid][parts[0]] = float(parts[1])
            break
    return matrix


def _shannon(abundances: dict[str, float]) -> float:
    total = sum(abundances.values()) or 1.0
    h = 0.0
    for v in abundances.values():
        p = v / total
        if p > 0:
            h -= p * math.log(p)
    return h


def _bray_curtis(a: dict[str, float], b: dict[str, float]) -> float:
    taxa = set(a) | set(b)
    num = sum(abs(a.get(t, 0.0) - b.get(t, 0.0)) for t in taxa)
    den = sum(a.get(t, 0.0) + b.get(t, 0.0) for t in taxa) or 1.0
    return num / den


def _mock_group_effect(sample_id: str, group: str | None, genus: str) -> float:
    """Deterministic mock shift for IBD vs control demos."""
    base = {"Bacteroides": 0.25, "Faecalibacterium": 0.18, "Escherichia": 0.04}.get(genus, 0.05)
    if group and group.lower() in {"ibd", "disease", "case", "patient"}:
        if genus == "Faecalibacterium":
            return base * 0.4
        if genus == "Escherichia":
            return base * 2.5
    return base


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"]) / "diversity_analysis"
    biomarker_dir = Path(state["outdir"]) / "biomarkers"
    outdir.mkdir(parents=True, exist_ok=True)
    biomarker_dir.mkdir(parents=True, exist_ok=True)

    matrix = _load_genus_matrix(state.get("artifacts", {}).get("taxonomy_profile"), state.get("artifacts", {}))
    samples = state.get("samples", [])
    groups = {s["sample_id"]: (s.get("group") or "unknown") for s in samples}

    # If single group and query mentions IBD, synthesize control/case labels for mock demos
    if len(set(groups.values())) <= 1 and state.get("mode") == "mock":
        for i, s in enumerate(samples):
            groups[s["sample_id"]] = "IBD" if i % 2 == 0 else "Control"
            # adjust matrix for demo biomarkers
            sid = s["sample_id"]
            if sid not in matrix:
                matrix[sid] = {}
            for g in ("Bacteroides", "Faecalibacterium", "Escherichia", "Prevotella"):
                matrix[sid][g] = _mock_group_effect(sid, groups[sid], g)

    # Alpha diversity
    alpha_lines = ["sample\tgroup\tshannon\trichness"]
    for sid, abund in matrix.items():
        alpha_lines.append(f"{sid}\t{groups.get(sid, 'unknown')}\t{_shannon(abund):.4f}\t{len(abund)}")
    alpha_path = outdir / "alpha_diversity.tsv"
    alpha_path.write_text("\n".join(alpha_lines) + "\n", encoding="utf-8")

    # Beta diversity (pairwise Bray-Curtis)
    ids = sorted(matrix)
    beta_lines = ["sample_a\tsample_b\tbray_curtis"]
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            beta_lines.append(f"{a}\t{b}\t{_bray_curtis(matrix[a], matrix[b]):.4f}")
    beta_path = outdir / "beta_diversity.tsv"
    beta_path.write_text("\n".join(beta_lines) + "\n", encoding="utf-8")

    # Differential abundance / biomarkers (simple fold-change between groups)
    group_names = sorted({g for g in groups.values() if g != "unknown"})
    biomarker_rows = ["genus\tgroup_a\tgroup_b\tmean_a\tmean_b\tlog2fc\tdirection"]
    biomarkers: list[dict[str, Any]] = []
    if len(group_names) >= 2:
        ga, gb = group_names[0], group_names[1]
        taxa = set()
        for abund in matrix.values():
            taxa |= set(abund)
        for genus in sorted(taxa):
            vals_a = [matrix[s][genus] for s, g in groups.items() if g == ga and genus in matrix[s]]
            vals_b = [matrix[s][genus] for s, g in groups.items() if g == gb and genus in matrix[s]]
            if not vals_a or not vals_b:
                continue
            ma, mb = sum(vals_a) / len(vals_a), sum(vals_b) / len(vals_b)
            log2fc = math.log2((mb + 1e-9) / (ma + 1e-9))
            if abs(log2fc) < 0.5:
                continue
            direction = f"enriched_in_{gb}" if log2fc > 0 else f"enriched_in_{ga}"
            biomarker_rows.append(f"{genus}\t{ga}\t{gb}\t{ma:.4f}\t{mb:.4f}\t{log2fc:.4f}\t{direction}")
            biomarkers.append(
                {"genus": genus, "log2fc": log2fc, "direction": direction, "mean_a": ma, "mean_b": mb}
            )

    biomarker_path = biomarker_dir / "biomarkers.tsv"
    biomarker_path.write_text("\n".join(biomarker_rows) + "\n", encoding="utf-8")

    stats = {
        "alpha_diversity": str(alpha_path),
        "beta_diversity": str(beta_path),
        "biomarkers": str(biomarker_path),
        "n_biomarkers": len(biomarkers),
        "biomarker_list": biomarkers[:20],
        "groups": groups,
        "methods": ["shannon", "bray_curtis", "fold_change_proxy_ANCOM-BC/LEfSe"],
    }
    (outdir / "statistics_summary.json").write_text(
        __import__("json").dumps({k: v for k, v in stats.items() if k != "biomarker_list"}, indent=2),
        encoding="utf-8",
    )
    return {"statistics": stats, **{"_statistics_state": stats}}
