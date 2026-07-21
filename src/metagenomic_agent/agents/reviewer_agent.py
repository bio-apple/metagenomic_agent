"""Scientific Reviewer Agent — peer-review style confidence / concerns / recommendations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.reasoning_log import log_decision


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"]) / "reviewer"
    outdir.mkdir(parents=True, exist_ok=True)

    critic = state.get("critic") or (state.get("artifacts") or {}).get("critic") or {}
    validation = state.get("validation") or {}
    stats = state.get("statistics") or (state.get("artifacts") or {}).get("statistics") or {}
    evidence = (state.get("artifacts") or {}).get("evidence_integration") or {}
    n_samples = len(state.get("samples") or [])
    concerns: list[str] = []
    recommendations: list[str] = []

    # Data layer
    if n_samples < 6:
        concerns.append("insufficient samples for robust differential abundance")
        recommendations.append("recruit additional samples or treat findings as exploratory")
    bio_qc = (critic.get("details") or {}).get("bio_qc") or {}
    if bio_qc.get("ok") is False:
        concerns.append("bio QC chain reported failures (MAG/unclassified gates)")
        recommendations.append("inspect critic/bio_qc_chain.json and re-run affected steps")
    for sid, s in ((critic.get("details") or {}).get("samples") or {}).items():
        if float(s.get("host_fraction") or 0) > 0.5:
            concerns.append(f"possible host contamination / batch-like host signal in {sid}")
            recommendations.append("strengthen host depletion; check batch covariates")
        if float(s.get("read_retention") or 1) < 0.4:
            concerns.append(f"low sequencing depth / retention in {sid}")
            recommendations.append("increase sequencing depth or loosen QC with caution")

    # Analysis layer
    methods = stats.get("methods") or []
    if "mannwhitney_u" in methods and "r_export_deseq2_maaslin2_ancombc" not in str(methods):
        recommendations.append("for submission, run biomarkers/r_export DESeq2/MaAsLin2/ANCOM-BC")
    if not stats.get("biomarker_list"):
        concerns.append("no biomarkers detected — statistical power or filter may be too strict")

    # Biology layer
    n_ev = int(evidence.get("n_biomarkers") or 0)
    if n_ev and n_ev < 2:
        concerns.append("thin evidence integration — few grounded biomarker–literature links")
    for w in critic.get("warnings") or []:
        if w not in concerns:
            concerns.append(str(w)[:200])
    recommendations.extend(list(critic.get("recommendations") or [])[:5])

    # Confidence heuristic
    confidence = 0.9
    confidence -= 0.08 * min(len(concerns), 5)
    if n_samples >= 10:
        confidence += 0.05
    if critic.get("passed") is False:
        confidence -= 0.15
    if validation.get("biological", {}).get("passed") is False:
        confidence -= 0.1
    confidence = round(max(0.2, min(0.98, confidence)), 2)

    review = {
        "role": "scientific_reviewer",
        "confidence": confidence,
        "concerns": concerns,
        "recommendation": recommendations,
        "layers": {
            "data": [c for c in concerns if any(k in c.lower() for k in ("sample", "depth", "contamin", "host", "batch"))],
            "analysis": [c for c in concerns if any(k in c.lower() for k in ("biomarker", "statistical", "filter", "power"))],
            "biology": [c for c in concerns if c not in concerns[:0] and "evidence" in c.lower()],
        },
        "passed": confidence >= 0.55 and critic.get("passed", True) is not False,
    }
    (outdir / "review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    concern_lines = [f"- {c}" for c in concerns] or ["- none"]
    rec_lines = [f"- {r}" for r in recommendations] or ["- none"]
    md = [
        "# Scientific Reviewer",
        "",
        f"**confidence:** `{confidence}`",
        "",
        "## Concerns",
        *concern_lines,
        "",
        "## Recommendations",
        *rec_lines,
        "",
    ]
    (outdir / "review.md").write_text("\n".join(md), encoding="utf-8")

    reason = log_decision(
        state,
        "reviewer",
        f"Peer-review confidence={confidence}",
        f"concerns={len(concerns)}; passed={review['passed']}",
    )
    arts = {**(state.get("artifacts") or {}), **(reason.get("artifacts") or {}), "reviewer": review}
    # Also surface as critic-compatible for routing
    critic_out = {
        **critic,
        "passed": review["passed"],
        "warnings": list(dict.fromkeys(list(critic.get("warnings") or []) + concerns)),
        "recommendations": list(dict.fromkeys(list(critic.get("recommendations") or []) + recommendations)),
        "reviewer": review,
    }
    return {
        "critic": critic_out,
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [f"Scientific Reviewer: confidence={confidence}; concerns={len(concerns)}"],
    }
