"""Compositional differential abundance: CLR transform + Mann-Whitney (ANCOM-like light)."""

from __future__ import annotations

import math
from typing import Any


def clr_transform(abund: dict[str, float], pseudocount: float = 1e-6) -> dict[str, float]:
    vals = {k: max(v, 0.0) + pseudocount for k, v in abund.items()}
    logv = {k: math.log(v) for k, v in vals.items()}
    mean = sum(logv.values()) / len(logv)
    return {k: lv - mean for k, lv in logv.items()}


def ancom_like(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str],
    fdr: float = 0.1,
) -> list[dict[str, Any]]:
    """Lightweight compositional test: CLR then MWU + BH-FDR. Not full ANCOM-BC."""
    from metagenomic_agent.agents.statistics_agent import _bh_fdr, _mannwhitney_u

    group_names = sorted({g for g in groups.values() if g != "unknown"})
    if len(group_names) < 2:
        return []
    ga, gb = group_names[0], group_names[1]
    clr = {sid: clr_transform(ab) for sid, ab in matrix.items()}
    taxa = set()
    for ab in matrix.values():
        taxa |= set(ab)
    raw: list[tuple[str, float, float, float]] = []
    for genus in sorted(taxa):
        a = [clr[s].get(genus, 0.0) for s, g in groups.items() if g == ga and s in clr]
        b = [clr[s].get(genus, 0.0) for s, g in groups.items() if g == gb and s in clr]
        if len(a) < 2 or len(b) < 2:
            continue
        _, p = _mannwhitney_u(a, b)
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        raw.append((genus, ma, mb, p))
    qvals = _bh_fdr([r[3] for r in raw])
    out = []
    for (genus, ma, mb, p), q in zip(raw, qvals):
        if q > fdr:
            continue
        out.append(
            {
                "genus": genus,
                "clr_mean_a": ma,
                "clr_mean_b": mb,
                "p_value": p,
                "q_value": q,
                "direction": f"enriched_in_{gb}" if mb > ma else f"enriched_in_{ga}",
                "method": "clr_mwu_bh",
            }
        )
    return out
