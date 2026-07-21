"""Statistics Agent — diversity + Mann-Whitney U with Benjamini-Hochberg FDR."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_genus_matrix(taxonomy_profile: str | None, artifacts: dict[str, Any]) -> dict[str, dict[str, float]]:
    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    path = taxonomy_profile or artifacts.get("taxonomy_profile")
    if path and Path(path).exists():
        for line in Path(path).read_text().splitlines()[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                sample, genus, abund = parts[0], parts[1], float(parts[2])
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


def _mannwhitney_u(x: list[float], y: list[float]) -> tuple[float, float]:
    """Two-sided Mann-Whitney U with normal approximation (no scipy dependency)."""
    n1, n2 = len(x), len(y)
    if n1 < 1 or n2 < 1:
        return float("nan"), 1.0
    combined = [(v, 0) for v in x] + [(v, 1) for v in y]
    combined.sort(key=lambda t: t[0])
    # average ranks for ties
    ranks = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg
        i = j
    r1 = sum(ranks[k] for k, (_, g) in enumerate(combined) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    u = min(u1, u2)
    mu = n1 * n2 / 2.0
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0) or 1.0
    z = (u - mu) / sigma
    # two-sided p from erfc
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return u, max(0.0, min(1.0, p))


def _bh_fdr(pvalues: list[float]) -> list[float]:
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    adj = [0.0] * m
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = m - rank  # 0-based rank from end
        # standard BH: p * m / (rank) where rank is 1..m in ascending p order
        r = m - i
        val = min(prev, pvalues[order[r - 1]] * m / r)
        adj[order[r - 1]] = val
        prev = val
    # Fix BH properly
    order_asc = sorted(range(m), key=lambda i: pvalues[i])
    q = [0.0] * m
    running = 1.0
    for i in range(m - 1, -1, -1):
        idx = order_asc[i]
        rank = i + 1
        running = min(running, pvalues[idx] * m / rank)
        q[idx] = min(1.0, running)
    return q


def _synthetic_demo_matrix(n_case: int = 3, n_ctrl: int = 3) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """Explicit demo data when demo_mode=true (not silent odd/even labeling)."""
    matrix: dict[str, dict[str, float]] = {}
    groups: dict[str, str] = {}
    for i in range(n_case):
        sid = f"case_{i+1}"
        groups[sid] = "IBD"
        matrix[sid] = {
            "Bacteroides": 0.22,
            "Faecalibacterium": 0.06,
            "Escherichia": 0.12,
            "Prevotella": 0.10,
            "Other": 0.50,
        }
    for i in range(n_ctrl):
        sid = f"ctrl_{i+1}"
        groups[sid] = "Control"
        matrix[sid] = {
            "Bacteroides": 0.25,
            "Faecalibacterium": 0.20,
            "Escherichia": 0.03,
            "Prevotella": 0.12,
            "Other": 0.40,
        }
    return matrix, groups


def _filter_low_frequency(
    matrix: dict[str, dict[str, float]],
    *,
    min_prevalence: float,
    min_rel_abundance: float,
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Drop ultra-low-frequency OTU/ASV/genus features after HITL-confirmed thresholds."""
    if not matrix:
        return matrix, {"n_before": 0, "n_after": 0, "removed": []}
    n = len(matrix)
    taxa: set[str] = set()
    for abund in matrix.values():
        taxa |= set(abund)
    keep: set[str] = set()
    removed: list[str] = []
    for t in taxa:
        present = 0
        max_ab = 0.0
        for abund in matrix.values():
            v = float(abund.get(t) or 0.0)
            max_ab = max(max_ab, v)
            if v >= min_rel_abundance:
                present += 1
        prev = present / n if n else 0.0
        if prev >= min_prevalence and max_ab >= min_rel_abundance:
            keep.add(t)
        else:
            removed.append(t)
    filtered = {sid: {t: v for t, v in abund.items() if t in keep} for sid, abund in matrix.items()}
    return filtered, {
        "n_before": len(taxa),
        "n_after": len(keep),
        "n_removed": len(removed),
        "removed_preview": removed[:40],
        "min_prevalence": min_prevalence,
        "min_rel_abundance": min_rel_abundance,
    }


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"]) / "diversity_analysis"
    biomarker_dir = Path(state["outdir"]) / "biomarkers"
    outdir.mkdir(parents=True, exist_ok=True)
    biomarker_dir.mkdir(parents=True, exist_ok=True)

    matrix = _load_genus_matrix(state.get("artifacts", {}).get("taxonomy_profile"), state.get("artifacts", {}))
    samples = state.get("samples", [])
    groups = {s["sample_id"]: (s.get("group") or "unknown") for s in samples}
    stats_cfg = state.get("config", {}).get("statistics", {}) or {}
    demo_mode = bool(stats_cfg.get("demo_mode", False))
    notes: list[str] = []

    real_groups = {g for g in groups.values() if g != "unknown"}
    if len(real_groups) < 2:
        if demo_mode or state.get("mode") == "mock":
            matrix, groups = _synthetic_demo_matrix()
            notes.append("demo_mode: used synthetic case/control matrix for differential demo (not real sample labels)")
        else:
            notes.append("Insufficient group labels for differential abundance; diversity-only")

    # HITL-confirmed OTU/ASV (genus-feature) prevalence filter
    min_prev = float(stats_cfg.get("min_prevalence", 0.1))
    min_ab = float(stats_cfg.get("min_rel_abundance", 1e-5))
    matrix, filter_meta = _filter_low_frequency(matrix, min_prevalence=min_prev, min_rel_abundance=min_ab)
    notes.append(
        f"OTU/ASV filter preset={stats_cfg.get('otu_filter_preset', 'custom')}: "
        f"kept {filter_meta['n_after']}/{filter_meta['n_before']} features "
        f"(prevalence≥{min_prev}, rel_ab≥{min_ab})"
    )
    (outdir / "otu_asv_filter.json").write_text(
        __import__("json").dumps(filter_meta, indent=2), encoding="utf-8"
    )

    alpha_lines = ["sample\tgroup\tshannon\trichness"]
    for sid, abund in matrix.items():
        alpha_lines.append(f"{sid}\t{groups.get(sid, 'unknown')}\t{_shannon(abund):.4f}\t{len(abund)}")
    alpha_path = outdir / "alpha_diversity.tsv"
    alpha_path.write_text("\n".join(alpha_lines) + "\n", encoding="utf-8")

    ids = sorted(matrix)
    beta_lines = ["sample_a\tsample_b\tbray_curtis"]
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            beta_lines.append(f"{a}\t{b}\t{_bray_curtis(matrix[a], matrix[b]):.4f}")
    beta_path = outdir / "beta_diversity.tsv"
    beta_path.write_text("\n".join(beta_lines) + "\n", encoding="utf-8")

    biomarker_rows = ["genus\tgroup_a\tgroup_b\tmean_a\tmean_b\tlog2fc\tp_value\tq_value\tdirection"]
    biomarkers: list[dict[str, Any]] = []
    group_names = sorted({g for g in groups.values() if g != "unknown"})
    if len(group_names) >= 2:
        ga, gb = group_names[0], group_names[1]
        taxa = set()
        for abund in matrix.values():
            taxa |= set(abund)
        raw: list[tuple[str, float, float, float, float, float]] = []
        for genus in sorted(taxa):
            vals_a = [matrix[s][genus] for s, g in groups.items() if g == ga and genus in matrix[s]]
            vals_b = [matrix[s][genus] for s, g in groups.items() if g == gb and genus in matrix[s]]
            if len(vals_a) < 2 or len(vals_b) < 2:
                continue
            ma, mb = sum(vals_a) / len(vals_a), sum(vals_b) / len(vals_b)
            log2fc = math.log2((mb + 1e-9) / (ma + 1e-9))
            _, p = _mannwhitney_u(vals_a, vals_b)
            raw.append((genus, ma, mb, log2fc, p, 0.0))
        qvals = _bh_fdr([r[4] for r in raw])
        for (genus, ma, mb, log2fc, p, _), q in zip(raw, qvals):
            if q > 0.25 and abs(log2fc) < 0.5:
                continue
            direction = f"enriched_in_{gb}" if log2fc > 0 else f"enriched_in_{ga}"
            biomarker_rows.append(
                f"{genus}\t{ga}\t{gb}\t{ma:.4f}\t{mb:.4f}\t{log2fc:.4f}\t{p:.4g}\t{q:.4g}\t{direction}"
            )
            biomarkers.append(
                {"genus": genus, "log2fc": log2fc, "p_value": p, "q_value": q, "direction": direction, "mean_a": ma, "mean_b": mb}
            )

    biomarker_path = biomarker_dir / "biomarkers.tsv"
    biomarker_path.write_text("\n".join(biomarker_rows) + "\n", encoding="utf-8")

    methods = [
        "shannon_alpha",
        "bray_curtis_beta",
        "mannwhitney_u",
        "benjamini_hochberg_fdr",
    ]
    cfg_stats = (state.get("config") or {}).get("statistics") or {}
    enable_lefse = bool(cfg_stats.get("lefse_like", True))
    enable_ancom = bool(cfg_stats.get("ancom_like", True))
    lefse_rows: list[dict[str, Any]] = []
    ancom_rows: list[dict[str, Any]] = []
    if len(group_names) >= 2:
        from metagenomic_agent.stats.lefse_like import lefse_like
        from metagenomic_agent.stats.compositional import ancom_like

        if enable_lefse:
            lefse_rows = lefse_like(matrix, groups)
            methods.append("lefse_like_cohen_d")
            lefse_path = biomarker_dir / "lefse_like.tsv"
            lines = ["genus\tgroup\tlda_score\tlog2fc\tp_value"]
            for r in lefse_rows:
                lines.append(
                    f"{r['genus']}\t{r['group']}\t{r['lda_score']}\t{r['log2fc']:.4f}\t{r['p_value']:.4g}"
                )
            lefse_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if enable_ancom:
            ancom_rows = ancom_like(matrix, groups)
            methods.append("clr_mwu_bh_ancom_like")
            ancom_path = biomarker_dir / "ancom_like.tsv"
            lines = ["genus\tclr_mean_a\tclr_mean_b\tp_value\tq_value\tdirection"]
            for r in ancom_rows:
                lines.append(
                    f"{r['genus']}\t{r['clr_mean_a']:.4f}\t{r['clr_mean_b']:.4f}\t"
                    f"{r['p_value']:.4g}\t{r['q_value']:.4g}\t{r['direction']}"
                )
            ancom_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Persist genus matrix for downstream viz
    mat_path = outdir / "genus_matrix.tsv"
    all_taxa = sorted({t for ab in matrix.values() for t in ab})
    mat_lines = ["sample\t" + "\t".join(all_taxa)]
    for sid in sorted(matrix):
        mat_lines.append(sid + "\t" + "\t".join(str(matrix[sid].get(t, 0.0)) for t in all_taxa))
    mat_path.write_text("\n".join(mat_lines) + "\n", encoding="utf-8")

    (outdir / "notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")

    stats = {
        "alpha_diversity": str(alpha_path),
        "beta_diversity": str(beta_path),
        "genus_matrix": str(mat_path),
        "biomarkers": str(biomarker_path),
        "lefse_like": str(biomarker_dir / "lefse_like.tsv") if lefse_rows else None,
        "ancom_like": str(biomarker_dir / "ancom_like.tsv") if ancom_rows else None,
        "n_biomarkers": len(biomarkers),
        "biomarker_list": biomarkers[:20],
        "lefse_list": lefse_rows[:20],
        "ancom_list": ancom_rows[:20],
        "groups": groups,
        "methods": methods + ["otu_asv_prevalence_filter"],
        "notes": notes,
        "otu_asv_filter": filter_meta,
        "disclaimer": (
            "Default differential abundance: Mann-Whitney U + BH-FDR. "
            "Also exports lefse_like (Cohen's d proxy) and ancom_like (CLR+MWU). "
            "Ultra-low-frequency features are culled using HITL-confirmed prevalence thresholds. "
            "These are lightweight Python approximations — for journal submission prefer "
            "official LEfSe / ANCOM-BC / MaAsLin2 on exported tables."
        ),
    }
    (outdir / "statistics_summary.json").write_text(
        __import__("json").dumps(
            {k: v for k, v in stats.items() if k not in {"biomarker_list", "lefse_list", "ancom_list"}},
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"statistics": stats, "_statistics_state": stats, "artifacts": {**state.get("artifacts", {}), "statistics": stats}}
