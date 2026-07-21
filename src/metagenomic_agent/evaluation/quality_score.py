"""Run-level data quality scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def compute_quality_scores(state: dict[str, Any]) -> dict[str, Any]:
    artifacts = state.get("artifacts") or {}
    qc = artifacts.get("qc_host") or {}
    tax = artifacts.get("taxonomy") or {}
    mags = artifacts.get("mags") or artifacts.get("assembly") or {}

    retentions = [float(v.get("read_retention", 1.0)) for v in qc.values()] if qc else [0.85]
    hosts = [float(v.get("host_fraction", 0.0)) for v in qc.values()] if qc else [0.1]
    class_rates = [float(v.get("classification_rate", 0.5)) for v in tax.values()] if tax else [0.5]

    coverage = _clamp(100.0 * (sum(retentions) / len(retentions)))
    contamination_proxy = _clamp(100.0 * (1.0 - sum(hosts) / len(hosts)))
    taxonomy_ok = _clamp(100.0 * (sum(class_rates) / len(class_rates)))

    completeness = 70.0
    assembly_score = 60.0
    if isinstance(mags, dict):
        bins = mags.get("bins") or mags.get("checkm") or []
        if isinstance(bins, list) and bins:
            comps = [float(b.get("completeness", 0)) for b in bins if isinstance(b, dict)]
            conts = [float(b.get("contamination", 100)) for b in bins if isinstance(b, dict)]
            if comps:
                completeness = _clamp(sum(comps) / len(comps))
                assembly_score = _clamp(completeness - (sum(conts) / len(conts) if conts else 0))
        elif mags.get("contigs") or mags.get("status") == "ok":
            assembly_score = 80.0
            completeness = 75.0

    # Profiling-only runs: weight assembly lower
    enable_asm = bool((state.get("config") or {}).get("pipeline", {}).get("enable_assembly"))
    if not enable_asm:
        overall = 0.35 * coverage + 0.25 * contamination_proxy + 0.40 * taxonomy_ok
        assembly_score = max(assembly_score, 70.0)  # N/A-ish baseline
        completeness = max(completeness, 70.0)
    else:
        overall = (
            0.25 * coverage
            + 0.25 * assembly_score
            + 0.25 * contamination_proxy
            + 0.25 * completeness
        )

    scores = {
        "Coverage": round(coverage, 1),
        "Assembly": round(assembly_score, 1),
        "Contamination": round(contamination_proxy, 1),
        "Completeness": round(completeness, 1),
        "Taxonomy": round(taxonomy_ok, 1),
        "Overall Score": round(overall, 1),
    }
    return {
        "scores": scores,
        "passed": overall >= 60.0,
        "notes": [
            "Contamination score is inverted host fraction (higher = cleaner non-host signal).",
            "Assembly/Completeness reflect MAG CheckM when available; otherwise profiling baselines.",
        ],
    }


def write_quality_report(state: dict[str, Any]) -> dict[str, Any]:
    report = compute_quality_scores(state)
    out = Path(state["outdir"]) / "quality"
    out.mkdir(parents=True, exist_ok=True)
    (out / "quality_scores.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Data Quality Scores", ""]
    for k, v in report["scores"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    for n in report["notes"]:
        lines.append(f"- {n}")
    (out / "quality_scores.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["path"] = str(out / "quality_scores.md")
    return report
