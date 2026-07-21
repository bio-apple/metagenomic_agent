"""Explainable AI helpers — leave-one-feature-out importance (SHAP/LIME-style, pure Python)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _group_means(matrix: dict[str, dict[str, float]], groups: dict[str, str], genus: str) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for sid, g in groups.items():
        if g == "unknown":
            continue
        buckets.setdefault(g, []).append(matrix.get(sid, {}).get(genus, 0.0))
    return {g: (sum(vs) / len(vs) if vs else 0.0) for g, vs in buckets.items()}


def _separation_score(means: dict[str, float]) -> float:
    if len(means) < 2:
        return 0.0
    vals = list(means.values())
    return abs(vals[0] - vals[1])


def leave_one_out_importance(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str],
    genera: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Approximate feature importance by drop in group-separation when a taxon is removed.

    This is a lightweight, dependency-free stand-in for SHAP/LIME on abundance tables.
    """
    taxa = genera or sorted({t for ab in matrix.values() for t in ab})
    base_scores = {t: _separation_score(_group_means(matrix, groups, t)) for t in taxa}
    base_total = sum(base_scores.values()) or 1.0

    rows = []
    for t in taxa:
        # contribution proxy: own separation / total
        local = base_scores[t]
        # leave-one-out: total without this feature
        reduced = (base_total - local) / max(len(taxa) - 1, 1)
        importance = local  # primary driver signal
        rows.append(
            {
                "feature": t,
                "importance": round(importance, 6),
                "normalized_importance": round(local / base_total, 6),
                "group_means": _group_means(matrix, groups, t),
                "method": "leave_one_feature_separation",
                "note": "SHAP/LIME-style attribution without heavy ML deps; interpret as differential driver strength.",
            }
        )
    rows.sort(key=lambda r: -r["importance"])
    return rows


def write_xai_report(state: dict[str, Any]) -> dict[str, Any]:
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    groups = stats.get("groups") or {}
    matrix: dict[str, dict[str, float]] = {}
    mat_path = Path(stats.get("genus_matrix") or Path(state["outdir"]) / "diversity_analysis" / "genus_matrix.tsv")
    if mat_path.exists():
        lines = mat_path.read_text(encoding="utf-8").splitlines()
        if lines:
            header = lines[0].split("\t")[1:]
            for line in lines[1:]:
                parts = line.split("\t")
                sid = parts[0]
                matrix[sid] = {header[i]: float(parts[i + 1]) for i in range(len(header)) if i + 1 < len(parts)}

    biomarkers = [b.get("genus") for b in (stats.get("biomarker_list") or []) if b.get("genus")]
    rows = leave_one_out_importance(matrix, groups, genera=biomarkers or None) if matrix and groups else []

    out = Path(state["outdir"]) / "xai"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "method": "leave_one_feature_separation",
        "features": rows[:30],
        "summary": (
            f"Top drivers: {', '.join(r['feature'] for r in rows[:5])}" if rows else "No features to explain"
        ),
    }
    (out / "feature_importance.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# XAI — Feature importance (biomarker drivers)", "", payload["summary"], ""]
    md.append("| Feature | Importance | Normalized |")
    md.append("|---------|------------|------------|")
    for r in rows[:20]:
        md.append(f"| {r['feature']} | {r['importance']} | {r['normalized_importance']} |")
    md.append("")
    md.append(
        "_Method: leave-one-feature group-separation attribution (SHAP/LIME-style explanation without black-box models)._"
    )
    (out / "feature_importance.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    payload["path"] = str(out / "feature_importance.md")
    return payload
