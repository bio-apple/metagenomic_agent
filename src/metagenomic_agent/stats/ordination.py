"""Pure-Python classical MDS (PCoA) from a distance matrix."""

from __future__ import annotations

import math
from typing import Any


def _zeros(n: int, m: int) -> list[list[float]]:
    return [[0.0] * m for _ in range(n)]


def distance_matrix_from_pairs(ids: list[str], pairs: dict[tuple[str, str], float]) -> list[list[float]]:
    n = len(ids)
    d = _zeros(n, n)
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i == j:
                continue
            key = (a, b) if (a, b) in pairs else (b, a)
            d[i][j] = float(pairs.get(key, 0.0))
    return d


def classical_mds(dist: list[list[float]], n_components: int = 2) -> tuple[list[list[float]], list[float]]:
    """Classical multidimensional scaling (PCoA). Returns coordinates and eigenvalues."""
    n = len(dist)
    if n == 0:
        return [], []
    # Double centering of -0.5 * D^2
    d2 = [[dist[i][j] ** 2 for j in range(n)] for i in range(n)]
    row_mean = [sum(row) / n for row in d2]
    col_mean = [sum(d2[i][j] for i in range(n)) / n for j in range(n)]
    grand = sum(row_mean) / n
    b = _zeros(n, n)
    for i in range(n):
        for j in range(n):
            b[i][j] = -0.5 * (d2[i][j] - row_mean[i] - col_mean[j] + grand)

    # Power iteration for top eigenvectors
    coords = _zeros(n, n_components)
    eigenvalues: list[float] = []
    residual = [row[:] for row in b]
    for k in range(n_components):
        v = [1.0 / math.sqrt(n)] * n
        for _ in range(80):
            w = [sum(residual[i][j] * v[j] for j in range(n)) for i in range(n)]
            norm = math.sqrt(sum(x * x for x in w)) or 1.0
            v = [x / norm for x in w]
        # Rayleigh quotient
        bv = [sum(residual[i][j] * v[j] for j in range(n)) for i in range(n)]
        lam = sum(v[i] * bv[i] for i in range(n))
        eigenvalues.append(lam)
        scale = math.sqrt(max(lam, 0.0))
        for i in range(n):
            coords[i][k] = v[i] * scale
        # Deflate
        for i in range(n):
            for j in range(n):
                residual[i][j] -= lam * v[i] * v[j]
    return coords, eigenvalues


def pcoa_from_beta_tsv(beta_tsv: str, sample_groups: dict[str, str] | None = None) -> dict[str, Any]:
    from pathlib import Path

    path = Path(beta_tsv)
    pairs: dict[tuple[str, str], float] = {}
    ids: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                a, b, d = parts[0], parts[1], float(parts[2])
                pairs[(a, b)] = d
                ids.add(a)
                ids.add(b)
    ordered = sorted(ids)
    if len(ordered) < 2:
        return {"points": [], "method": "classical_mds", "note": "need >=2 samples"}
    dist = distance_matrix_from_pairs(ordered, pairs)
    coords, eigs = classical_mds(dist, n_components=2)
    total = sum(max(e, 0.0) for e in eigs) or 1.0
    points = []
    for i, sid in enumerate(ordered):
        points.append(
            {
                "sample": sid,
                "PC1": coords[i][0],
                "PC2": coords[i][1],
                "group": (sample_groups or {}).get(sid, "unknown"),
            }
        )
    return {
        "type": "scatter",
        "title": "PCoA (classical MDS on Bray-Curtis)",
        "method": "classical_mds",
        "points": points,
        "eigenvalues": eigs,
        "variance_explained": [max(e, 0.0) / total for e in eigs],
        "note": "Computed from beta_diversity.tsv via classical MDS (pure Python).",
    }
