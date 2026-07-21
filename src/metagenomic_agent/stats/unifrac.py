"""UniFrac-lite: phylogenetic beta diversity without requiring an external tree file.

Uses a synthetic genus-level tree (shared kingdom→phylum→class→order→family→genus
depths via a curated or hash-based hierarchy) suitable for CI/mock and Methods disclosure.
For publication, prefer UniFrac on a reference phylogeny (e.g. MetaPhlAn / Greengenes2).
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

# Minimal gut/environment hierarchy hints (genus → path of ancestors)
_CURATED: dict[str, list[str]] = {
    "Faecalibacterium": ["Bacteria", "Firmicutes", "Clostridia", "Eubacteriales", "Oscillospiraceae"],
    "Bacteroides": ["Bacteria", "Bacteroidota", "Bacteroidia", "Bacteroidales", "Bacteroidaceae"],
    "Prevotella": ["Bacteria", "Bacteroidota", "Bacteroidia", "Bacteroidales", "Prevotellaceae"],
    "Escherichia": ["Bacteria", "Proteobacteria", "Gammaproteobacteria", "Enterobacterales", "Enterobacteriaceae"],
    "Bifidobacterium": ["Bacteria", "Actinobacteriota", "Actinomycetia", "Actinomycetales", "Bifidobacteriaceae"],
    "Akkermansia": ["Bacteria", "Verrucomicrobiota", "Verrucomicrobiae", "Verrucomicrobiales", "Akkermansiaceae"],
    "Roseburia": ["Bacteria", "Firmicutes", "Clostridia", "Eubacteriales", "Lachnospiraceae"],
    "Fusobacterium": ["Bacteria", "Fusobacteriota", "Fusobacteriia", "Fusobacteriales", "Fusobacteriaceae"],
}


def _lineage(taxon: str) -> list[str]:
    if taxon in _CURATED:
        return _CURATED[taxon] + [taxon]
    # Hash-based stable pseudo-hierarchy so unknown taxa still share random deep branches
    h = hashlib.md5(taxon.encode()).hexdigest()
    return [
        "Bacteria",
        f"P_{h[0:2]}",
        f"C_{h[2:4]}",
        f"O_{h[4:6]}",
        f"F_{h[6:8]}",
        taxon,
    ]


def _branch_lengths(path: list[str]) -> dict[str, float]:
    """Edge id → length (unit depth)."""
    edges: dict[str, float] = {}
    for i in range(1, len(path)):
        edges[f"{path[i-1]}->{path[i]}"] = 1.0
    return edges


def _sample_branch_weights(abund: dict[str, float]) -> dict[str, float]:
    total = sum(abund.values()) or 1.0
    weights: dict[str, float] = {}
    for tax, v in abund.items():
        p = (v / total) if v > 0 else 0.0
        if p <= 0:
            continue
        for edge, length in _branch_lengths(_lineage(tax)).items():
            weights[edge] = weights.get(edge, 0.0) + p * length
    return weights


def weighted_unifrac(a: dict[str, float], b: dict[str, float]) -> float:
    """Weighted UniFrac on synthetic tree; returns [0, 1]-ish distance."""
    wa, wb = _sample_branch_weights(a), _sample_branch_weights(b)
    edges = set(wa) | set(wb)
    if not edges:
        return 0.0
    num = 0.0
    den = 0.0
    for e in edges:
        xa, xb = wa.get(e, 0.0), wb.get(e, 0.0)
        num += abs(xa - xb)
        den += xa + xb
    if den <= 0:
        return 0.0
    return min(1.0, num / den)


def unifrac_distance_matrix(matrix: dict[str, dict[str, float]]) -> tuple[list[str], list[list[float]]]:
    ids = sorted(matrix)
    n = len(ids)
    dist = [[0.0] * n for _ in range(n)]
    for i, a in enumerate(ids):
        for j in range(i + 1, n):
            d = weighted_unifrac(matrix[a], matrix[ids[j]])
            dist[i][j] = dist[j][i] = d
    return ids, dist


def unifrac_summary(matrix: dict[str, dict[str, float]]) -> dict[str, Any]:
    ids, dist = unifrac_distance_matrix(matrix)
    pairs = []
    for i, a in enumerate(ids):
        for j in range(i + 1, len(ids)):
            pairs.append({"sample_a": a, "sample_b": ids[j], "weighted_unifrac": round(dist[i][j], 6)})
    return {
        "method": "weighted_unifrac_lite",
        "note": "Synthetic genus tree; use reference phylogeny UniFrac for publication.",
        "n_samples": len(ids),
        "mean_distance": round(
            sum(p["weighted_unifrac"] for p in pairs) / max(1, len(pairs)), 6
        )
        if pairs
        else 0.0,
        "pairs": pairs[:200],
        "distance_matrix_ids": ids,
        "distance_matrix": dist,
    }
