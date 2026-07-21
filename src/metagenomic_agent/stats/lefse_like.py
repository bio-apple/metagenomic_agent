"""LEfSe-like biomarker ranking (Kruskal/MWU + effect size; no R dependency)."""

from __future__ import annotations

import math
from typing import Any


def _mwu_p(x: list[float], y: list[float]) -> float:
    from metagenomic_agent.agents.statistics_agent import _mannwhitney_u

    _, p = _mannwhitney_u(x, y)
    return p


def lefse_like(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str],
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """Rank taxa by group separation with LDA-style effect size proxy (mean difference / pooled sd)."""
    group_names = sorted({g for g in groups.values() if g != "unknown"})
    if len(group_names) < 2:
        return []
    ga, gb = group_names[0], group_names[1]
    taxa = set()
    for abund in matrix.values():
        taxa |= set(abund)
    rows: list[dict[str, Any]] = []
    for genus in sorted(taxa):
        vals_a = [matrix[s].get(genus, 0.0) for s, g in groups.items() if g == ga]
        vals_b = [matrix[s].get(genus, 0.0) for s, g in groups.items() if g == gb]
        if len(vals_a) < 2 or len(vals_b) < 2:
            continue
        ma, mb = sum(vals_a) / len(vals_a), sum(vals_b) / len(vals_b)
        var_a = sum((v - ma) ** 2 for v in vals_a) / max(len(vals_a) - 1, 1)
        var_b = sum((v - mb) ** 2 for v in vals_b) / max(len(vals_b) - 1, 1)
        pooled = math.sqrt((var_a + var_b) / 2.0) or 1e-9
        effect = abs(mb - ma) / pooled  # Cohen's d proxy used as LDA score stand-in
        p = _mwu_p(vals_a, vals_b)
        if p > alpha and effect < 0.5:
            continue
        rows.append(
            {
                "genus": genus,
                "group": gb if mb > ma else ga,
                "lda_score": round(effect, 4),
                "log2fc": math.log2((mb + 1e-9) / (ma + 1e-9)),
                "p_value": p,
                "method": "lefse_like_cohen_d",
            }
        )
    rows.sort(key=lambda r: -r["lda_score"])
    return rows
