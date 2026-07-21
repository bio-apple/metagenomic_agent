"""Principal Investigator Agent — review evidence/critic and optionally replan."""

from __future__ import annotations

from typing import Any

from metagenomic_agent.messaging import append_msg, emit


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    """PI synthesizes run status and may request one replan cycle."""
    critic = state.get("critic") or {}
    validation = state.get("validation") or {}
    evidence = (state.get("artifacts") or {}).get("evidence_table") or []
    quality = ((state.get("artifacts") or {}).get("quality_scores") or {}).get("scores") or {}
    pi_retries = int((state.get("artifacts") or {}).get("pi_retries") or 0)
    max_pi = int((state.get("config") or {}).get("pi", {}).get("max_replans", 1))

    findings = []
    if not critic.get("passed", True):
        findings.extend(critic.get("warnings") or [])
    findings.extend((validation.get("biological") or {}).get("warnings") or [])
    overall = quality.get("Overall Score")
    if overall is not None and float(overall) < 60:
        findings.append(f"Low overall data quality score: {overall}")

    decision = "accept"
    replan = False
    if findings and pi_retries < max_pi:
        # Replan only for recoverable tool/QC issues
        blob = " ".join(findings).lower()
        if any(k in blob for k in ("quality", "retention", "contract", "classification", "oom", "metaphlan")):
            decision = "replan"
            replan = True

    report = {
        "decision": decision,
        "findings": findings[:12],
        "n_evidence": len(evidence),
        "quality_overall": overall,
        "pi_retries": pi_retries + (1 if replan else 0),
        "summary": (
            f"PI Agent {decision}: {len(findings)} finding(s), "
            f"{len(evidence)} evidence row(s), quality={overall}"
        ),
    }
    arts = dict(state.get("artifacts") or {})
    arts["pi_review"] = report
    if replan:
        arts["pi_retries"] = pi_retries + 1
        # Soft hints for self-heal / supervisor
        arts.setdefault("errors", []).append(
            {"node": "pi_agent", "error": "; ".join(findings[:3]), "classified": "logic"}
        )

    amsg = emit("pi", "supervisor" if replan else "report", "request" if replan else "result", report)
    return {
        "artifacts": arts,
        "messages": state.get("messages", []) + [report["summary"]],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
        "pi_replan": replan,
    }
