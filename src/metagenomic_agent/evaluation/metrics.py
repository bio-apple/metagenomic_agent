"""Research evaluation metrics for paper-facing benchmarks."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def precision_at_k(predicted: list[str], truth: list[str], k: int = 5) -> float:
    if k <= 0:
        return 0.0
    top = predicted[:k]
    if not top:
        return 0.0
    hits = sum(1 for p in top if p in set(truth))
    return hits / len(top)


def mag_quality_summary(checkm_tsv: str | Path) -> dict[str, Any]:
    path = Path(checkm_tsv)
    if not path.exists():
        return {"n": 0, "mean_completeness": 0.0, "mean_contamination": 0.0, "hq_bins": 0}
    comps, conts = [], []
    for line in path.read_text().splitlines()[1:]:
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        try:
            c, x = float(parts[1]), float(parts[2])
        except ValueError:
            continue
        comps.append(c)
        conts.append(x)
    hq = sum(1 for c, x in zip(comps, conts) if c >= 90 and x <= 5)
    return {
        "n": len(comps),
        "mean_completeness": sum(comps) / len(comps) if comps else 0.0,
        "mean_contamination": sum(conts) / len(conts) if conts else 0.0,
        "hq_bins": hq,
    }


def evaluate_run(outdir: str | Path, golden: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score a completed mock/real run against optional golden expectations."""
    root = Path(outdir)
    golden = golden or {}
    report = {
        "final_report_exists": (root / "final_report.html").exists(),
        "taxonomy_profile_exists": (root / "taxonomy_profile.tsv").exists(),
        "biomarkers_exists": (root / "biomarkers" / "biomarkers.tsv").exists(),
        "events_log_exists": (root / "logs" / "events.jsonl").exists(),
    }

    # Biomarker genus ranking
    pred: list[str] = []
    bio = root / "biomarkers" / "biomarkers.tsv"
    if bio.exists():
        for line in bio.read_text().splitlines()[1:]:
            parts = line.split("\t")
            if parts:
                pred.append(parts[0])
    truth = list(golden.get("biomarker_genera") or ["Faecalibacterium", "Escherichia"])
    report["biomarker_precision_at_5"] = precision_at_k(pred, truth, k=5)

    # MAG quality if present
    mag_checks = list(root.glob("**/demo.checkm2.tsv")) + list(root.glob("**/*.checkm2.tsv"))
    if mag_checks:
        report["mag_quality"] = mag_quality_summary(mag_checks[0])

    report["passed"] = bool(report["final_report_exists"] and report["taxonomy_profile_exists"])
    return report
