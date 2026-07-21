"""Plan Validator Agent — logic completeness & domain constraints (anti-hallucination)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.domain_kb import missing_domain_constraints
from metagenomic_agent.messaging import append_msg, emit


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    dag = state.get("dag") or []
    if not dag:
        issues.append("Empty execution DAG — supervisor produced no runnable nodes.")

    # Logical completeness: taxonomy before statistics; QC before taxonomy
    agents = [n.get("agent") for n in dag]
    ids = {n.get("id"): n for n in dag}
    for n in dag:
        for dep in n.get("depends_on") or []:
            if dep not in ids and dep not in {x.get("id") for x in dag}:
                warnings.append(f"Node {n.get('id')} depends on missing node '{dep}'")

    if "statistics" in agents and "taxonomy" not in agents:
        issues.append("Statistics planned without taxonomy profiling upstream.")
    if "taxonomy" in agents and "qc" not in agents and "qc_host" not in agents:
        warnings.append("Taxonomy without explicit QC node — ensure reads are pre-cleaned.")

    # Tool specialist missing required params (non-mock)
    for spec in ((state.get("artifacts") or {}).get("tool_specialist") or {}).get("specialists") or []:
        if spec.get("missing_required"):
            issues.append(f"Tool {spec.get('tool')} missing required params: {spec['missing_required']}")
        if spec.get("status") == "registered_for_routing" and state.get("mode") not in {"mock"}:
            warnings.append(
                f"Tool {spec.get('tool')} is registered for scientific routing but may not be installed locally."
            )

    # Domain constraints — ask, don't guess
    questions = missing_domain_constraints(state)
    issues.extend(questions)

    passed = len(issues) == 0
    report = {
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "n_dag_nodes": len(dag),
        "policy": "safety_first_ask_dont_guess",
    }

    out = Path(state["outdir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan_validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    hitl = list(state.get("hitl_pending") or [])
    updates: dict[str, Any] = {
        "artifacts": {**state.get("artifacts", {}), "plan_validation": report},
        "messages": state.get("messages", [])
        + [f"Plan Validator: {'PASS' if passed else 'BLOCK'} ({len(issues)} issue(s), {len(warnings)} warning(s))"],
        "agent_messages": append_msg(
            state.get("agent_messages"),
            emit("plan_validator", "hitl" if not passed else "executor", "warning" if not passed else "result", report),
        ),
    }

    if not passed:
        hitl.extend(issues[:8])
        updates["hitl_pending"] = hitl
        hard = bool((state.get("config") or {}).get("validation", {}).get("plan_validator_hard_fail", False))
        # Default: require HITL confirmation (auto_confirm may still proceed in CI)
        if hard or (not state.get("hitl_auto_confirm") and not (state.get("config") or {}).get("hitl", {}).get("auto_confirm", True)):
            updates["hitl_resolved"] = False
            updates["error"] = "plan_validator_blocked: " + "; ".join(issues[:3])

    return updates
