"""Automated bioinformatics QC chain — MAG CheckM2 + taxonomy classification quality."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

MagTier = Literal["high", "medium", "low", "fail", "missing"]


def mag_thresholds(config: dict[str, Any] | None = None) -> dict[str, float]:
    """Unified thresholds from config.validation (single source of truth)."""
    v = (config or {}).get("validation") or {}
    return {
        "high_completeness": float(v.get("mag_high_completeness", 90)),
        "high_contamination": float(v.get("mag_high_contamination", 5)),
        "medium_completeness": float(v.get("min_mag_completeness", 50)),
        "medium_contamination": float(v.get("max_mag_contamination", 10)),
    }


def taxonomy_thresholds(config: dict[str, Any] | None = None) -> dict[str, float]:
    v = (config or {}).get("validation") or {}
    return {
        "min_classification_rate": float(v.get("min_classification_rate", 0.3)),
        "max_unclassified_fraction": float(v.get("max_unclassified_fraction", 0.5)),
    }


def classify_mag_quality(
    completeness: float | None,
    contamination: float | None,
    config: dict[str, Any] | None = None,
) -> MagTier:
    if completeness is None and contamination is None:
        return "missing"
    comp = float(completeness if completeness is not None else 0)
    cont = float(contamination if contamination is not None else 100)
    t = mag_thresholds(config)
    if comp >= t["high_completeness"] and cont <= t["high_contamination"]:
        return "high"
    if comp >= t["medium_completeness"] and cont <= t["medium_contamination"]:
        return "medium"
    if comp <= 0 and cont >= 100:
        return "fail"
    return "low"


def parse_unclassified_fraction(
    *,
    classification_rate: float | None = None,
    unclassified_fraction: float | None = None,
    report_path: str | None = None,
) -> float | None:
    """Prefer explicit unclassified; else 1 - classification_rate; else parse Kraken report."""
    if unclassified_fraction is not None:
        return float(unclassified_fraction)
    if classification_rate is not None and classification_rate > 0:
        return max(0.0, min(1.0, 1.0 - float(classification_rate)))
    if report_path and Path(report_path).exists():
        try:
            for line in Path(report_path).read_text(encoding="utf-8").splitlines():
                # Kraken2 report: pct  clade  taxReads  ...  taxName
                parts = line.split("\t")
                if len(parts) >= 6 and parts[5].strip().lower() in {"unclassified", "u"}:
                    return float(parts[0]) / 100.0
                if len(parts) >= 1 and "unclassified" in line.lower() and parts[0].replace(".", "").isdigit():
                    return float(parts[0]) / 100.0
        except (OSError, ValueError):
            return None
    return None


def check_taxonomy_qc(
    *,
    classification_rate: float | None,
    unclassified_fraction: float | None = None,
    sample_id: str = "",
    tool: str = "kraken2/metaphlan",
    config: dict[str, Any] | None = None,
    report_path: str | None = None,
) -> dict[str, Any]:
    thr = taxonomy_thresholds(config)
    uncl = parse_unclassified_fraction(
        classification_rate=classification_rate,
        unclassified_fraction=unclassified_fraction,
        report_path=report_path,
    )
    rate = float(classification_rate) if classification_rate is not None else (
        (1.0 - uncl) if uncl is not None else None
    )
    warnings: list[str] = []
    recommendations: list[str] = []
    ok = True
    prefix = f"{sample_id}: " if sample_id else ""

    if rate is not None and rate < thr["min_classification_rate"]:
        ok = False
        warnings.append(
            f"{prefix}classification_rate={rate:.2f} < {thr['min_classification_rate']} ({tool})"
        )
        recommendations.append(
            "更换/更新分类数据库（Kraken2 DB / MetaPhlAn marker DB），或提高测序深度"
        )
    if uncl is not None and uncl > thr["max_unclassified_fraction"]:
        ok = False
        warnings.append(
            f"{prefix}unclassified_fraction={uncl:.2f} > {thr['max_unclassified_fraction']} ({tool})"
        )
        recommendations.append(
            "提高 --confidence（Kraken2）或检查宿主去除；必要时换用更匹配环境的参考库"
        )

    return {
        "ok": ok,
        "sample_id": sample_id,
        "tool": tool,
        "classification_rate": rate,
        "unclassified_fraction": uncl,
        "thresholds": thr,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def check_mag_qc(
    *,
    completeness: float | None,
    contamination: float | None,
    sample_id: str = "",
    n_bins: int | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tier = classify_mag_quality(completeness, contamination, config)
    t = mag_thresholds(config)
    warnings: list[str] = []
    recommendations: list[str] = []
    prefix = f"{sample_id}: " if sample_id else ""

    if tier == "missing":
        return {
            "ok": True,
            "tier": tier,
            "sample_id": sample_id,
            "completeness": completeness,
            "contamination": contamination,
            "n_bins": n_bins,
            "thresholds": t,
            "warnings": [],
            "recommendations": [],
            "high_quality_gate": {
                "completeness_min": t["high_completeness"],
                "contamination_max": t["high_contamination"],
            },
        }

    if tier == "high":
        ok = True
    elif tier == "medium":
        ok = True  # medium passes soft gate; still warn vs high-quality target
        warnings.append(
            f"{prefix}CheckM2 tier=medium "
            f"(comp={completeness}, cont={contamination}); "
            f"high-quality gate is ≥{t['high_completeness']}% / ≤{t['high_contamination']}%"
        )
        recommendations.append("精修分箱或提高组装深度以达到 high-quality MAG（≥90% / ≤5%）")
    else:
        ok = False
        warnings.append(
            f"{prefix}CheckM2 tier={tier} "
            f"(completeness={completeness}, contamination={contamination}); "
            f"fails medium gate ≥{t['medium_completeness']}% / ≤{t['medium_contamination']}%"
        )
        recommendations.append("重新分箱（MetaBAT2/MaxBin2）或改用 MEGAHIT 后重跑 CheckM2")

    # Explicit high-quality enforcement flag for reporting
    hq = tier == "high"
    if not hq and tier != "missing":
        if not any("high-quality" in w for w in warnings):
            warnings.append(
                f"{prefix}未达 high-quality MAG：Completeness>{t['high_completeness']}% 且 "
                f"Contamination<{t['high_contamination']}%"
            )

    return {
        "ok": ok,
        "tier": tier,
        "high_quality": hq,
        "sample_id": sample_id,
        "completeness": completeness,
        "contamination": contamination,
        "n_bins": n_bins,
        "thresholds": t,
        "warnings": warnings,
        "recommendations": list(dict.fromkeys(recommendations)),
        "high_quality_gate": {
            "completeness_min": t["high_completeness"],
            "contamination_max": t["high_contamination"],
        },
    }


def run_bio_qc_chain(state: dict[str, Any]) -> dict[str, Any]:
    """Full QC chain over taxonomy + MAG artifacts."""
    cfg = state.get("config") or {}
    arts = state.get("artifacts") or {}
    tax = arts.get("taxonomy") or {}
    assembly = arts.get("assembly") or {}
    sample_reports: dict[str, Any] = {}
    warnings: list[str] = []
    recommendations: list[str] = []
    mag_tiers: dict[str, str] = {}

    for sample in state.get("samples") or []:
        sid = sample.get("sample_id") or ""
        s_tax = tax.get(sid) or {}
        tool = "kraken2" if s_tax.get("kraken2_report") or s_tax.get("kraken2_abundance") else "metaphlan"
        tqc = check_taxonomy_qc(
            classification_rate=s_tax.get("classification_rate"),
            unclassified_fraction=s_tax.get("unclassified_fraction"),
            sample_id=sid,
            tool=tool,
            config=cfg,
            report_path=s_tax.get("kraken2_report") or s_tax.get("metaphlan_abundance"),
        )
        s_asm = assembly.get(sid) or {}
        mqc = check_mag_qc(
            completeness=s_asm.get("completeness"),
            contamination=s_asm.get("contamination"),
            sample_id=sid,
            n_bins=s_asm.get("n_bins"),
            config=cfg,
        )
        mag_tiers[sid] = mqc["tier"]
        sample_reports[sid] = {"taxonomy": tqc, "mag": mqc}
        warnings.extend(tqc["warnings"])
        warnings.extend(mqc["warnings"])
        recommendations.extend(tqc["recommendations"])
        recommendations.extend(mqc["recommendations"])

    ok = all(
        (r["taxonomy"]["ok"] and r["mag"]["ok"]) for r in sample_reports.values()
    ) if sample_reports else True

    return {
        "ok": ok,
        "samples": sample_reports,
        "mag_tiers": mag_tiers,
        "warnings": list(dict.fromkeys(warnings)),
        "recommendations": list(dict.fromkeys(recommendations)),
        "policy": "checkm2_hq_90_5_and_taxonomy_unclassified_gates",
        "thresholds": {
            "mag": mag_thresholds(cfg),
            "taxonomy": taxonomy_thresholds(cfg),
        },
    }
