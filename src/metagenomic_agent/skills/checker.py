"""Contract check node — pre/post validation between planner and executor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.messaging import append_msg, emit
from metagenomic_agent.skills.contracts import Severity
from metagenomic_agent.skills.playbooks import enforce_playbook_on_dag, select_playbooks
from metagenomic_agent.skills.registry import get_skill
from metagenomic_agent.skills.contracts import check_preconditions
from metagenomic_agent.state import AgentState


def contract_check(state: AgentState) -> dict[str, Any]:
    """Pre-execution contract + playbook enforcement.

    On ERROR violations: add HITL items and optionally block if auto_confirm is false.
    """
    dag = list(state.get("dag") or [])
    samples = state.get("samples") or []
    artifacts = dict(state.get("artifacts") or {})
    qc = artifacts.get("qc_host") or {}

    playbooks = select_playbooks(state.get("user_query") or "")
    dag, pb_notes = enforce_playbook_on_dag(dag, playbooks)

    violations: list[dict[str, Any]] = []
    for node in dag:
        tools = node.get("params", {}).get("tools") or node.get("tools") or []
        for tool in tools:
            skill = get_skill(tool)
            if not skill:
                continue
            for sample in samples:
                upstream = qc.get(sample["sample_id"], {})
                # For first-pass QC, upstream may be empty — only check r1
                if tool == "fastp":
                    upstream = {}
                if tool == "filter_host" and not upstream:
                    # will run after fastp in same agent; soft-skip pre if clean_r1 absent yet
                    continue
                vs = check_preconditions(skill, sample, upstream)
                for v in vs:
                    violations.append(
                        {
                            "skill": v.skill,
                            "check": v.check,
                            "message": v.message,
                            "severity": v.severity.value,
                            "details": v.details,
                            "node": node["id"],
                            "sample": sample["sample_id"],
                        }
                    )

    errors = [v for v in violations if v["severity"] == Severity.ERROR.value]
    warnings = [v for v in violations if v["severity"] == Severity.WARNING.value]

    outdir = Path(state["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    report = {
        "playbooks": [p.name for p in playbooks],
        "playbook_notes": pb_notes,
        "violations": violations,
        "n_errors": len(errors),
        "n_warnings": len(warnings),
    }
    (outdir / "contract_check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    hitl = list(state.get("hitl_pending") or [])
    messages = list(state.get("messages") or [])
    messages.append(
        f"Contract check: {len(playbooks)} playbook(s), {len(errors)} error(s), {len(warnings)} warning(s)"
    )
    messages.extend(pb_notes)

    updates: dict[str, Any] = {
        "dag": dag,
        "artifacts": {**artifacts, "contract_check": report, "playbooks": [p.name for p in playbooks]},
        "messages": messages,
        "agent_messages": append_msg(
            state.get("agent_messages"),
            emit("contract", "executor", "warning" if errors else "log", report),
        ),
    }

    if errors:
        hitl.append(
            "Contract pre-condition errors: "
            + "; ".join(e["message"] for e in errors[:5])
            + (" ..." if len(errors) > 5 else "")
        )
        updates["hitl_pending"] = hitl
        artifacts_err = list(artifacts.get("errors") or [])
        blocking = [e for e in errors if "Missing required artifact 'r1'" in e["message"]]
        hard = bool((state.get("config") or {}).get("validation", {}).get("contract_hard_fail", False))
        if hard:
            # Hard-fail: block execution path via error + HITL reject signal
            updates["error"] = "contract_hard_fail: " + "; ".join(e["message"] for e in errors[:5])
            updates["hitl_resolved"] = False
            updates["artifacts"] = {
                **updates["artifacts"],
                "errors": artifacts_err
                + [{"node": "contract_check", "error": e["message"], "classified": "logic"} for e in errors],
                "contract_hard_fail": True,
            }
            updates["messages"] = messages + ["Contract HARD FAIL — aborting swarm execution"]
        elif blocking:
            updates["artifacts"] = {
                **updates["artifacts"],
                "errors": artifacts_err
                + [{"node": "contract_check", "error": e["message"], "classified": "logic"} for e in blocking],
            }

    return updates


def check_skill_post(skill_name: str, outputs: dict[str, Any]) -> list[dict[str, Any]]:
    from metagenomic_agent.skills.contracts import check_postconditions

    skill = get_skill(skill_name)
    if not skill:
        return []
    return [
        {
            "skill": v.skill,
            "check": v.check,
            "message": v.message,
            "severity": v.severity.value,
            "details": v.details,
        }
        for v in check_postconditions(skill, outputs)
    ]
