"""QC & Critic Agent — Q20/Q30, contamination, CheckM completeness + biology review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.domain_rag import retrieve_tool_manuals
from metagenomic_agent.state import CriticResult


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    artifacts = state.get("artifacts", {})
    warnings: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"samples": {}, "mags": {}, "role": "qc_critic"}

    # CheckM2 quality gates from tool manual
    checkm_manual = (retrieve_tool_manuals("checkm2", tool="checkm2", top_k=1) or [{}])[0]
    gates = (checkm_manual.get("quality_gates") or {}).get("medium_quality") or {
        "completeness_min": 50,
        "contamination_max": 10,
    }
    comp_min = float(gates.get("completeness_min", 50))
    cont_max = float(gates.get("contamination_max", 10))

    for sample in state.get("samples", []):
        sid = sample["sample_id"]
        qc = artifacts.get("qc_host", {}).get(sid, {})
        tax = artifacts.get("taxonomy", {}).get(sid, {})
        retention = float(qc.get("read_retention", 1.0))
        host = float(qc.get("host_fraction", 0.0))
        rate = float(tax.get("classification_rate", 0.0))
        q30 = float(qc.get("Q30") or 0)
        q20 = float(qc.get("Q20") or qc.get("q20") or 0)
        # Derive Q20 proxy from Q30 when mock/tools omit Q20
        if not q20 and q30:
            q20 = min(100.0, q30 + 3.0)
        details["samples"][sid] = {
            "read_retention": retention,
            "host_fraction": host,
            "classification_rate": rate,
            "Q20": q20,
            "Q30": q30,
            "contamination_proxy_host_fraction": host,
        }
        if retention < 0.3:
            warnings.append(f"{sid}: low read retention after QC ({retention:.2f})")
            recommendations.append("Loosen fastp quality thresholds or inspect raw data integrity")
        if host > 0.8:
            warnings.append(f"{sid}: high host contamination ({host:.2f})")
            recommendations.append("Strengthen host removal or verify sample type")
        elif host > 0.2:
            warnings.append(f"{sid}: elevated host contamination ({host:.2f})")
            recommendations.append("Review host index / KneadData settings (SOP env_gut_host_filter)")
        if rate and rate < 0.2:
            warnings.append("Low microbial classification rate")
            recommendations.append("Try MetaPhlAn4 profiling or microCafe gLM")
        if q30 and q30 < 80:
            warnings.append(f"{sid}: Q30 below 80 ({q30})")
            recommendations.append("Re-run FastQC/MultiQC and consider resequencing")
        if q20 and q20 < 90:
            warnings.append(f"{sid}: Q20 below 90 ({q20})")
            recommendations.append("Inspect per-base quality; tighten/trim adapters via fastp/Trimmomatic")

        # MAG / CheckM2 completeness & contamination
        asm = (artifacts.get("assembly") or artifacts.get("assembly_binning") or {}).get(sid) or {}
        completeness = asm.get("completeness")
        contamination = asm.get("contamination")
        if completeness is not None or contamination is not None:
            try:
                comp = float(completeness) if completeness is not None else None
                cont = float(contamination) if contamination is not None else None
            except (TypeError, ValueError):
                comp, cont = None, None
            details["mags"][sid] = {"completeness": comp, "contamination": cont, "gates": gates}
            if comp is not None and comp < comp_min:
                warnings.append(f"{sid}: CheckM completeness {comp} < {comp_min} (medium-quality gate)")
                recommendations.append("Re-bin or co-assemble; see CheckM2 / MAG QC SOP")
            if cont is not None and cont > cont_max:
                warnings.append(f"{sid}: CheckM contamination {cont} > {cont_max}")
                recommendations.append("Refine bins (MetaBAT2/MaxBin2) before GTDB-Tk/Bakta")

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
    from metagenomic_agent.coordinator.summary import get_llm_context

    details["llm_context_preview"] = get_llm_context(state, max_chars=2000)
    details["pipeline_summary_ref"] = (artifacts.get("pipeline_summary") or {}).get("path")
    critic: CriticResult = {
        "passed": passed,
        "warnings": list(dict.fromkeys(warnings)),
        "recommendations": list(dict.fromkeys(recommendations)),
        "details": details,
    }
    out = Path(state["outdir"]) / "critic"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "role": "qc_critic",
        "warning": warnings[0] if warnings else None,
        "recommendation": recommendations[0] if recommendations else None,
        "passed": passed,
        "all_warnings": critic["warnings"],
        "all_recommendations": critic["recommendations"],
        "checks": ["Q20", "Q30", "host_contamination", "CheckM_completeness_contamination", "contracts"],
        "checkm_gates": gates,
    }
    (out / "critic_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "qc_critic.md").write_text(
        "# QC & Critic\n\n"
        + "\n".join(f"- WARN: {w}" for w in payload["all_warnings"][:20])
        + ("\n\nAll gates passed.\n" if passed else "\n"),
        encoding="utf-8",
    )
    return {
        "critic": critic,
        "artifacts": {**artifacts, "critic": payload, "qc_critic": payload},
        "messages": state.get("messages", [])
        + [f"QC & Critic {'PASS' if passed else 'WARN'}: {len(warnings)} warning(s)"],
    }
