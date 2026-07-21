"""Genus co-occurrence network via Spearman correlation."""

from __future__ import annotations

import math
from typing import Any


def _spearman(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n and vals[order[j]] == vals[order[i]]:
                j += 1
            avg = (i + 1 + j) / 2.0
            for k in range(i, j):
                r[order[k]] = avg
            i = j
        return r

    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    denx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    deny = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    den = denx * deny or 1.0
    return num / den


def cooccurrence_network(
    matrix: dict[str, dict[str, float]],
    min_abs_corr: float = 0.6,
    max_nodes: int = 20,
) -> dict[str, Any]:
    samples = sorted(matrix)
    if len(samples) < 3:
        return {"nodes": [], "edges": [], "method": "spearman", "note": "need >=3 samples"}
    # top genera by mean abundance
    means: dict[str, float] = {}
    for ab in matrix.values():
        for g, v in ab.items():
            means[g] = means.get(g, 0.0) + v
    taxa = [g for g, _ in sorted(means.items(), key=lambda x: -x[1])[:max_nodes]]
    edges = []
    for i, a in enumerate(taxa):
        xa = [matrix[s].get(a, 0.0) for s in samples]
        for b in taxa[i + 1 :]:
            yb = [matrix[s].get(b, 0.0) for s in samples]
            rho = _spearman(xa, yb)
            if abs(rho) >= min_abs_corr:
                edges.append({"source": a, "target": b, "weight": round(rho, 4), "type": "spearman"})
    return {"nodes": taxa, "edges": edges, "method": "spearman", "threshold": min_abs_corr}
