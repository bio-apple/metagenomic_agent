"""QC & Critic Agent — automated bio QC chain + biology review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.state import CriticResult
from metagenomic_agent.validators.bio_qc import mag_thresholds, run_bio_qc_chain


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    artifacts = state.get("artifacts", {})
    warnings: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"samples": {}, "mags": {}, "role": "qc_critic"}
    cfg = state.get("config") or {}
    gates = mag_thresholds(cfg)

    # --- Automated bioinformatics QC chain (CheckM2 HQ + taxonomy unclassified) ---
    bio_qc = run_bio_qc_chain(state)
    warnings.extend(bio_qc.get("warnings") or [])
    recommendations.extend(bio_qc.get("recommendations") or [])
    details["bio_qc"] = {
        "ok": bio_qc.get("ok"),
        "mag_tiers": bio_qc.get("mag_tiers"),
        "thresholds": bio_qc.get("thresholds"),
    }

    for sample in state.get("samples", []):
        sid = sample["sample_id"]
        qc = artifacts.get("qc_host", {}).get(sid, {})
        tax = artifacts.get("taxonomy", {}).get(sid, {})
        retention = float(qc.get("read_retention", 1.0))
        host = float(qc.get("host_fraction", 0.0))
        rate = float(tax.get("classification_rate") or 0.0)
        uncl = tax.get("unclassified_fraction")
        if uncl is None and rate:
            uncl = max(0.0, 1.0 - rate)
        q30 = float(qc.get("Q30") or 0)
        q20 = float(qc.get("Q20") or qc.get("q20") or 0)
        if not q20 and q30:
            q20 = min(100.0, q30 + 3.0)
        sample_bio = (bio_qc.get("samples") or {}).get(sid) or {}
        details["samples"][sid] = {
            "read_retention": retention,
            "host_fraction": host,
            "classification_rate": rate,
            "unclassified_fraction": uncl,
            "Q20": q20,
            "Q30": q30,
            "taxonomy_qc": sample_bio.get("taxonomy"),
            "mag_qc": sample_bio.get("mag"),
        }
        if retention < float((cfg.get("validation") or {}).get("min_read_retention", 0.3)):
            warnings.append(f"{sid}: low read retention after QC ({retention:.2f})")
            recommendations.append("Loosen fastp quality thresholds or inspect raw data integrity")
        if host > 0.8:
            warnings.append(f"{sid}: high host contamination ({host:.2f})")
            recommendations.append("Strengthen host removal or verify sample type")
        elif host > 0.2:
            warnings.append(f"{sid}: elevated host contamination ({host:.2f})")
            recommendations.append("Review host index / KneadData settings (SOP env_gut_host_filter)")
        if q30 and q30 < 80:
            warnings.append(f"{sid}: Q30 below 80 ({q30})")
            recommendations.append("Re-run FastQC/MultiQC and consider resequencing")
        if q20 and q20 < 90:
            warnings.append(f"{sid}: Q20 below 90 ({q20})")
            recommendations.append("Inspect per-base quality; tighten/trim adapters via fastp/Trimmomatic")

        mag = sample_bio.get("mag") or {}
        if mag:
            details["mags"][sid] = mag

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

    warnings = list(dict.fromkeys(warnings))
    recommendations = list(dict.fromkeys(recommendations))
    passed = len(warnings) == 0
    from metagenomic_agent.coordinator.summary import get_llm_context

    details["llm_context_preview"] = get_llm_context(state, max_chars=2000)
    details["pipeline_summary_ref"] = (artifacts.get("pipeline_summary") or {}).get("path")
    critic: CriticResult = {
        "passed": passed,
        "warnings": warnings,
        "recommendations": recommendations,
        "details": details,
    }
    out = Path(state["outdir"]) / "critic"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "role": "qc_critic",
        "warning": warnings[0] if warnings else None,
        "recommendation": recommendations[0] if recommendations else None,
        "passed": passed,
        "all_warnings": warnings,
        "all_recommendations": recommendations,
        "checks": [
            "Q20",
            "Q30",
            "host_contamination",
            "CheckM2_high_quality_90_5",
            "taxonomy_unclassified",
            "contracts",
        ],
        "checkm_gates": {
            "high_completeness": gates["high_completeness"],
            "high_contamination": gates["high_contamination"],
            "medium_completeness": gates["medium_completeness"],
            "medium_contamination": gates["medium_contamination"],
        },
        "bio_qc": details["bio_qc"],
    }
    (out / "critic_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "bio_qc_chain.json").write_text(json.dumps(bio_qc, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "qc_critic.md").write_text(
        "# QC & Critic\n\n"
        f"- Bio QC chain ok: `{bio_qc.get('ok')}`\n"
        f"- MAG tiers: `{bio_qc.get('mag_tiers')}`\n\n"
        + "\n".join(f"- WARN: {w}" for w in warnings[:30])
        + ("\n\nAll gates passed.\n" if passed else "\n"),
        encoding="utf-8",
    )
    return {
        "critic": critic,
        "artifacts": {
            **artifacts,
            "critic": payload,
            "qc_critic": payload,
            "bio_qc": bio_qc,
        },
        "messages": state.get("messages", [])
        + [f"QC & Critic {'PASS' if passed else 'WARN'}: {len(warnings)} warning(s)"],
    }
