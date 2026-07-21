"""Association analysis: linear models, mixed-model lite, and ML feature ranking.

Supports microbe ↔ clinical / environmental covariates beyond binary group labels.
"""

from __future__ import annotations

import math
import random
from typing import Any


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denx = math.sqrt(sum((a - mx) ** 2 for a in x))
    deny = math.sqrt(sum((b - my) ** 2 for b in y))
    if denx * deny == 0:
        return 0.0
    return num / (denx * deny)


def _ols_slope(x: list[float], y: list[float]) -> tuple[float, float]:
    """Return (slope, r)."""
    n = len(x)
    if n < 3:
        return 0.0, 0.0
    mx = sum(x) / n
    my = sum(y) / n
    varx = sum((a - mx) ** 2 for a in x) or 1e-12
    slope = sum((a - mx) * (b - my) for a, b in zip(x, y)) / varx
    return slope, _pearson(x, y)


def linear_associations(
    matrix: dict[str, dict[str, float]],
    covariates: dict[str, dict[str, float]],
    *,
    top_k: int = 30,
) -> list[dict[str, Any]]:
    """OLS-style association of each taxon with each numeric covariate."""
    samples = sorted(set(matrix) & set(covariates))
    if len(samples) < 4:
        return []
    taxa = sorted({t for ab in matrix.values() for t in ab})
    cov_names = sorted({k for meta in covariates.values() for k in meta})
    rows: list[dict[str, Any]] = []
    for tax in taxa:
        y = [float(matrix[s].get(tax, 0.0)) for s in samples]
        if sum(1 for v in y if v > 0) < 2:
            continue
        for cov in cov_names:
            x = [float(covariates[s].get(cov, 0.0)) for s in samples]
            if len(set(round(v, 6) for v in x)) < 2:
                continue
            slope, r = _ols_slope(x, y)
            # crude two-sided p from erfc on Fisher z of r
            n = len(samples)
            if abs(r) >= 0.999:
                p = 0.0
            else:
                z = 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(max(n - 3, 1))
                p = math.erfc(abs(z) / math.sqrt(2.0))
            rows.append(
                {
                    "taxon": tax,
                    "covariate": cov,
                    "slope": round(slope, 6),
                    "r": round(r, 4),
                    "p_value": round(max(0.0, min(1.0, p)), 4),
                    "method": "ols_linear",
                    "n": n,
                }
            )
    rows.sort(key=lambda r: (r["p_value"], -abs(r["r"])))
    return rows[:top_k]


def mixed_model_lite(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str],
    subject: dict[str, str] | None = None,
    *,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Subject-aware association: compare within-subject means when subject IDs exist,
    else fall back to group mean differences (disclosed as mixed_model_lite)."""
    subject = subject or {}
    samples = [s for s in matrix if groups.get(s) and groups[s] != "unknown"]
    if len(samples) < 4:
        return []
    group_names = sorted({groups[s] for s in samples})
    if len(group_names) < 2:
        return []
    ga, gb = group_names[0], group_names[1]
    taxa = sorted({t for s in samples for t in matrix[s]})
    rows: list[dict[str, Any]] = []
    for tax in taxa:
        if subject:
            # average within subject then compare subjects by majority group
            by_subj: dict[str, list[float]] = {}
            subj_group: dict[str, str] = {}
            for s in samples:
                sid = subject.get(s, s)
                by_subj.setdefault(sid, []).append(float(matrix[s].get(tax, 0.0)))
                subj_group[sid] = groups[s]
            vals_a = [sum(v) / len(v) for sid, v in by_subj.items() if subj_group.get(sid) == ga]
            vals_b = [sum(v) / len(v) for sid, v in by_subj.items() if subj_group.get(sid) == gb]
            method = "mixed_model_lite_subject_mean"
        else:
            vals_a = [float(matrix[s].get(tax, 0.0)) for s in samples if groups[s] == ga]
            vals_b = [float(matrix[s].get(tax, 0.0)) for s in samples if groups[s] == gb]
            method = "mixed_model_lite_group_mean"
        if len(vals_a) < 2 or len(vals_b) < 2:
            continue
        ma, mb = sum(vals_a) / len(vals_a), sum(vals_b) / len(vals_b)
        # pooled t-ish statistic without scipy
        sa = sum((v - ma) ** 2 for v in vals_a) / max(1, len(vals_a) - 1)
        sb = sum((v - mb) ** 2 for v in vals_b) / max(1, len(vals_b) - 1)
        se = math.sqrt(sa / len(vals_a) + sb / len(vals_b)) or 1e-12
        t = (mb - ma) / se
        p = math.erfc(abs(t) / math.sqrt(2.0))
        rows.append(
            {
                "taxon": tax,
                "group_a": ga,
                "group_b": gb,
                "mean_a": round(ma, 6),
                "mean_b": round(mb, 6),
                "delta": round(mb - ma, 6),
                "p_value": round(max(0.0, min(1.0, p)), 4),
                "method": method,
            }
        )
    rows.sort(key=lambda r: r["p_value"])
    return rows[:top_k]


def ml_feature_importance(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str],
    *,
    n_trees: int = 25,
    top_k: int = 15,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Extremely randomized stump ensemble (pure Python) for feature ranking."""
    rng = random.Random(seed)
    samples = [s for s in matrix if groups.get(s) not in (None, "unknown")]
    labels = sorted({groups[s] for s in samples})
    if len(samples) < 4 or len(labels) < 2:
        return []
    # binary: first vs rest
    pos = labels[0]
    y = [1 if groups[s] == pos else 0 for s in samples]
    taxa = sorted({t for s in samples for t in matrix[s]})
    if not taxa:
        return []
    importance = {t: 0.0 for t in taxa}
    for _ in range(n_trees):
        # bootstrap indices
        idx = [rng.randrange(len(samples)) for _ in range(len(samples))]
        feat = taxa[rng.randrange(len(taxa))]
        xs = [float(matrix[samples[i]].get(feat, 0.0)) for i in idx]
        ys = [y[i] for i in idx]
        # best threshold = median
        thr = sorted(xs)[len(xs) // 2]
        left = [ys[j] for j, v in enumerate(xs) if v <= thr]
        right = [ys[j] for j, v in enumerate(xs) if v > thr]
        if not left or not right:
            continue
        def gini(vals: list[int]) -> float:
            if not vals:
                return 0.0
            p = sum(vals) / len(vals)
            return 2 * p * (1 - p)

        parent = gini(ys)
        split = (len(left) * gini(left) + len(right) * gini(right)) / len(ys)
        gain = parent - split
        if gain > 0:
            importance[feat] += gain
    ranked = sorted(importance.items(), key=lambda kv: -kv[1])
    return [
        {"taxon": t, "importance": round(v, 6), "positive_class": pos, "method": "extra_trees_lite"}
        for t, v in ranked[:top_k]
        if v > 0
    ]


def run_association_suite(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str],
    covariates: dict[str, dict[str, float]] | None = None,
    subject: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "linear": linear_associations(matrix, covariates or {}) if covariates else [],
        "mixed": mixed_model_lite(matrix, groups, subject=subject),
        "ml": ml_feature_importance(matrix, groups),
    }
