"""Batch-effect diagnostics for Statistical Reasoning / Critic self-correction."""

from __future__ import annotations

import math
from typing import Any

from metagenomic_agent.stats.ordination import classical_mds


def _bray(a: dict[str, float], b: dict[str, float]) -> float:
    taxa = set(a) | set(b)
    num = sum(abs(a.get(t, 0.0) - b.get(t, 0.0)) for t in taxa)
    den = sum(a.get(t, 0.0) + b.get(t, 0.0) for t in taxa) or 1.0
    return num / den


def batch_pca_dominance(
    matrix: dict[str, dict[str, float]],
    batch: dict[str, str],
    *,
    r2_warn: float = 0.35,
) -> dict[str, Any]:
    """Detect batch dominance via between/within Bray–Curtis ratio + PCoA PC1 η²."""
    samples = [s for s in sorted(matrix) if batch.get(s)]
    batches = {batch[s] for s in samples}
    if len(samples) < 4 or len(batches) < 2:
        return {
            "suspect": False,
            "pc1_batch_r2": 0.0,
            "between_within_ratio": 0.0,
            "n_batches": len(batches),
            "note": "insufficient samples/batches",
        }
    n = len(samples)
    dist = [[0.0] * n for _ in range(n)]
    within: list[float] = []
    between: list[float] = []
    for i, a in enumerate(samples):
        for j in range(i + 1, n):
            d = _bray(matrix[a], matrix[samples[j]])
            dist[i][j] = dist[j][i] = d
            if batch[a] == batch[samples[j]]:
                within.append(d)
            else:
                between.append(d)
    mean_w = sum(within) / len(within) if within else 0.0
    mean_b = sum(between) / len(between) if between else 0.0
    ratio = (mean_b / mean_w) if mean_w > 1e-12 else (10.0 if mean_b > 0 else 0.0)

    coords, _ = classical_mds(dist, n_components=1)
    pc1 = [coords[i][0] for i in range(n)]
    # If MDS collapses, fall back to first taxon axis as PC proxy
    if max(pc1) - min(pc1) < 1e-12:
        taxa = sorted({t for s in samples for t in matrix[s]})
        tax = taxa[0] if taxa else None
        pc1 = [float(matrix[s].get(tax, 0.0)) for s in samples] if tax else pc1
    mean = sum(pc1) / n
    ss_tot = sum((v - mean) ** 2 for v in pc1) or 1e-12
    by_b: dict[str, list[float]] = {}
    for i, s in enumerate(samples):
        by_b.setdefault(batch[s], []).append(pc1[i])
    ss_between = 0.0
    for vals in by_b.values():
        m = sum(vals) / len(vals)
        ss_between += len(vals) * (m - mean) ** 2
    r2 = ss_between / ss_tot
    # Suspect if PC1~batch strong OR between-batch distances >> within-batch
    suspect = r2 >= r2_warn or ratio >= 1.5
    return {
        "suspect": suspect,
        "pc1_batch_r2": round(r2, 4),
        "between_within_ratio": round(ratio, 4),
        "mean_within_bray": round(mean_w, 4),
        "mean_between_bray": round(mean_b, 4),
        "n_batches": len(batches),
        "batch_counts": {k: len(v) for k, v in by_b.items()},
        "recommendation": (
            "PCA/PCoA dominated by batch — adjust for batch (MaAsLin3 fixed effect / combat-like) and re-run"
            if suspect
            else "batch not dominant on PC1"
        ),
        "method": "pcoa_pc1_batch_eta2_plus_bray_ratio",
    }


def residualize_by_batch(
    matrix: dict[str, dict[str, float]],
    batch: dict[str, str],
) -> dict[str, dict[str, float]]:
    """Simple batch mean-centering per taxon (combat-like lite); renormalize to relative abundance."""
    samples = [s for s in matrix if batch.get(s)]
    if not samples:
        return matrix
    taxa = sorted({t for s in samples for t in matrix[s]})
    batch_means: dict[str, dict[str, float]] = {}
    global_mean: dict[str, float] = {}
    for t in taxa:
        by_b: dict[str, list[float]] = {}
        all_v: list[float] = []
        for s in samples:
            v = float(matrix[s].get(t, 0.0))
            by_b.setdefault(batch[s], []).append(v)
            all_v.append(v)
        global_mean[t] = sum(all_v) / len(all_v) if all_v else 0.0
        batch_means[t] = {b: (sum(vs) / len(vs) if vs else 0.0) for b, vs in by_b.items()}
    out: dict[str, dict[str, float]] = {}
    for s in matrix:
        if s not in batch:
            out[s] = dict(matrix[s])
            continue
        b = batch[s]
        adj = {}
        for t in taxa:
            v = float(matrix[s].get(t, 0.0))
            adj[t] = max(0.0, v - batch_means[t].get(b, 0.0) + global_mean[t])
        total = sum(adj.values()) or 1.0
        out[s] = {t: adj[t] / total for t in taxa}
    return out
