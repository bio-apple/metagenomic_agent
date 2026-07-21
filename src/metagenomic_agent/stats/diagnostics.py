"""Abundance-table diagnostics for Statistical Reasoning (Development.docx Priority 3)."""

from __future__ import annotations

import math
from typing import Any


def _matrix_arrays(matrix: dict[str, dict[str, float]]) -> tuple[list[str], list[str], list[list[float]]]:
    samples = sorted(matrix)
    taxa = sorted({t for ab in matrix.values() for t in ab})
    rows = [[float(matrix[s].get(t, 0.0)) for t in taxa] for s in samples]
    return samples, taxa, rows


def diagnose_abundance(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Detect compositionality proxies, zero inflation, and simple batch/group imbalance."""
    samples, taxa, rows = _matrix_arrays(matrix)
    n_s, n_t = len(samples), len(taxa)
    if n_s == 0 or n_t == 0:
        return {
            "n_samples": n_s,
            "n_taxa": n_t,
            "compositional": True,
            "zero_inflation": False,
            "zero_fraction": 0.0,
            "batch_effect_suspect": False,
            "recommended_diff_methods": ["mannwhitney_u_bh"],
            "recommended_diversity": {"alpha": ["shannon"], "beta": ["bray_curtis"]},
            "notes": ["empty matrix"],
        }

    flat = [v for row in rows for v in row]
    zeros = sum(1 for v in flat if v <= 0.0)
    zero_frac = zeros / max(1, len(flat))
    # Relative abundances that sum ~1 per sample → compositional
    row_sums = [sum(r) for r in rows]
    compositional = all(0.85 <= s <= 1.15 for s in row_sums if s > 0) or all(s > 0 for s in row_sums)
    zero_inflation = zero_frac >= 0.35

    groups = groups or {}
    group_vals = [groups.get(s, "unknown") for s in samples]
    known = [g for g in group_vals if g != "unknown"]
    batch_effect_suspect = False
    # Crude imbalance: one group << other
    if len(set(known)) >= 2:
        from collections import Counter

        c = Counter(known)
        sizes = list(c.values())
        if max(sizes) >= 3 * min(sizes):
            batch_effect_suspect = True

    # Method selection (Development.docx)
    if compositional and zero_inflation:
        diff = ["ancom_bc2", "aldex2", "maaslin3"]
    elif compositional:
        diff = ["ancom_bc2", "maaslin3", "clr_mwu"]
    else:
        diff = ["deseq2", "mannwhitney_u_bh"]
    if batch_effect_suspect:
        diff = ["maaslin3"] + [m for m in diff if m != "maaslin3"]

    diversity = {
        "alpha": ["shannon", "simpson"],
        "beta": ["bray_curtis", "weighted_unifrac"],
        "ordination_test": ["permanova"] if len(set(known)) >= 2 and len(known) >= 4 else [],
    }

    return {
        "n_samples": n_s,
        "n_taxa": n_t,
        "compositional": compositional,
        "zero_inflation": zero_inflation,
        "zero_fraction": round(zero_frac, 4),
        "batch_effect_suspect": batch_effect_suspect,
        "group_counts": {g: group_vals.count(g) for g in sorted(set(group_vals))},
        "recommended_diff_methods": diff,
        "recommended_diversity": diversity,
        "notes": [
            "Diagnostics are heuristic (no phylogeny for UniFrac).",
            "Journal methods exported via R scripts when available.",
        ],
    }


def simpson_index(abundances: dict[str, float]) -> float:
    total = sum(abundances.values()) or 1.0
    return 1.0 - sum((v / total) ** 2 for v in abundances.values() if v > 0)


def permanova_pseudo_f(
    dist: list[list[float]],
    labels: list[str],
    n_perm: int = 99,
) -> dict[str, Any]:
    """Lightweight PERMANOVA-style pseudo-F on a condensed distance matrix (square).

    Not a full vegan::adonis replacement — suitable for mock/CI and Methods disclosure.
    """
    import random

    n = len(labels)
    if n < 4 or len(dist) != n:
        return {"pseudo_f": float("nan"), "p_value": 1.0, "n_perm": 0, "method": "permanova_lite"}

    def ss_among(lab: list[str]) -> float:
        groups: dict[str, list[int]] = {}
        for i, g in enumerate(lab):
            groups.setdefault(g, []).append(i)
        if len(groups) < 2:
            return 0.0
        # sum of squared distances within vs total (Gower-like simplification)
        total = 0.0
        within = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                d2 = dist[i][j] ** 2
                total += d2
                if lab[i] == lab[j]:
                    within += d2
        among = total - within
        return among

    obs = ss_among(labels)
    # Normalize roughly by residual
    resid = 1e-9
    for i in range(n):
        for j in range(i + 1, n):
            if labels[i] != labels[j]:
                resid += dist[i][j] ** 2
    pseudo_f = obs / resid
    null = 0
    lab = list(labels)
    for _ in range(n_perm):
        random.shuffle(lab)
        if ss_among(lab) >= obs:
            null += 1
    p = (null + 1) / (n_perm + 1)
    return {
        "pseudo_f": round(pseudo_f, 6),
        "p_value": round(p, 4),
        "n_perm": n_perm,
        "method": "permanova_lite",
        "note": "Approximate PERMANOVA on Bray–Curtis; use vegan::adonis2 for publication.",
    }
