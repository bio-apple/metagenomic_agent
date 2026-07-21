"""Critic Agent — reliability + contract + biology context review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.state import CriticResult


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    artifacts = state.get("artifacts", {})
    warnings: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"samples": {}}

    for sample in state.get("samples", []):
        sid = sample["sample_id"]
        qc = artifacts.get("qc_host", {}).get(sid, {})
        tax = artifacts.get("taxonomy", {}).get(sid, {})
        retention = float(qc.get("read_retention", 1.0))
        host = float(qc.get("host_fraction", 0.0))
        rate = float(tax.get("classification_rate", 0.0))
        q30 = float(qc.get("Q30", 0))
        details["samples"][sid] = {
            "read_retention": retention,
            "host_fraction": host,
            "classification_rate": rate,
            "Q30": q30,
        }
        if retention < 0.3:
            warnings.append(f"{sid}: low read retention after QC ({retention:.2f})")
            recommendations.append("Loosen fastp quality thresholds or inspect raw data integrity")
        if host > 0.8:
            warnings.append(f"{sid}: high host contamination ({host:.2f})")
            recommendations.append("Strengthen host removal or verify sample type")
        if rate and rate < 0.2:
            warnings.append("Low microbial classification rate")
            recommendations.append("Try MetaPhlAn4 profiling or microCafe gLM")
        if q30 and q30 < 80:
            warnings.append(f"{sid}: Q30 below 80 ({q30})")
            recommendations.append("Re-run FastQC/MultiQC and consider resequencing")

    bio = (state.get("validation") or {}).get("biological") or {}
    for w in bio.get("warnings") or artifacts.get("biological_warnings") or []:
        warnings.append(w)
        recommendations.append("Review biological context warnings before interpreting biomarkers")

    for v in artifacts.get("contract_post") or []:
        if isinstance(v, dict) and v.get("severity") == "error":
            warnings.append(v.get("message", "contract post failure"))
            recommendations.append("Adjust tool parameters or switch taxonomy skill (contract)")

    stats = artifacts.get("statistics") or state.get("statistics") or {}
    if stats.get("n_biomarkers", 0) == 0 and any(
        k in (state.get("user_query") or "").lower() for k in ("biomarker", "标志", "ibd")
    ):
        warnings.append("No biomarkers detected despite biomarker-oriented query")
        recommendations.append("Check group metadata and increase sample size")

    q = (state.get("user_query") or "").lower()
    if any(k in q for k in ("gut", "肠道", "ibd", "fecal", "stool")):
        tops: set[str] = set()
        for art in artifacts.get("taxonomy", {}).values():
            tops |= set(art.get("top_genera") or [])
        markers = {"Bacteroides", "Faecalibacterium", "Prevotella", "Bifidobacterium"}
        if tops and not (tops & markers):
            warnings.append("Gut query but no typical gut marker genera found")
            recommendations.append("Verify taxonomy database and sample origin")

    passed = len(warnings) == 0
    critic: CriticResult = {
        "passed": passed,
        "warnings": list(dict.fromkeys(warnings)),
        "recommendations": list(dict.fromkeys(recommendations)),
        "details": details,
    }
    out = Path(state["outdir"]) / "critic"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "warning": warnings[0] if warnings else None,
        "recommendation": recommendations[0] if recommendations else None,
        "passed": passed,
        "all_warnings": critic["warnings"],
        "all_recommendations": critic["recommendations"],
    }
    (out / "critic_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "critic": critic,
        "artifacts": {**artifacts, "critic": payload},
        "messages": state.get("messages", []) + [f"Critic {'PASS' if passed else 'WARN'}: {len(warnings)} warning(s)"],
    }
