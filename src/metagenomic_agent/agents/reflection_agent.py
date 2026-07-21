"""Reflection Agent — ReAct-style evaluate/correct notes after tools + review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.reasoning_log import log_decision


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    """Observe results → evaluate → propose corrections (does not auto-mutate DAG unless flagged)."""
    outdir = Path(state["outdir"]) / "reflection"
    outdir.mkdir(parents=True, exist_ok=True)

    reviewer = (state.get("artifacts") or {}).get("reviewer") or {}
    critic = state.get("critic") or {}
    errors = (state.get("artifacts") or {}).get("errors") or []
    wf_ref = ((state.get("artifacts") or {}).get("workflow") or {}).get("reflection") or []

    observations = []
    if errors:
        observations.append(f"Observed {len(errors)} execution error(s)")
    if reviewer.get("concerns"):
        observations.append(f"Reviewer raised {len(reviewer['concerns'])} concern(s)")
    if critic.get("warnings"):
        observations.append(f"Critic warnings: {len(critic['warnings'])}")

    corrections: list[str] = []
    for c in reviewer.get("recommendation") or []:
        corrections.append(str(c))
    for t in wf_ref:
        corrections.append(f"workflow: {t}")
    if any("host" in str(x).lower() for x in (reviewer.get("concerns") or [])):
        corrections.append("Re-run QC with stronger host filter / verify host_index")
    if any("depth" in str(x).lower() or "retention" in str(x).lower() for x in (reviewer.get("concerns") or [])):
        corrections.append("Flag samples for resequencing; loosen fastp only if justified")

    reflection = {
        "role": "reflection",
        "loop": ["Question", "Reason", "Plan", "Execute", "Observe", "Evaluate", "Correct", "Answer"],
        "observations": observations,
        "evaluate": {
            "reviewer_confidence": reviewer.get("confidence"),
            "critic_passed": critic.get("passed"),
            "n_errors": len(errors),
        },
        "correct": corrections[:12],
        "needs_human": bool(reviewer.get("confidence") is not None and float(reviewer.get("confidence") or 1) < 0.55),
    }
    (outdir / "reflection.json").write_text(json.dumps(reflection, indent=2, ensure_ascii=False), encoding="utf-8")
    obs_lines = [f"- {o}" for o in observations] or [
        "- pipeline completed without major runtime errors logged"
    ]
    corr_lines = [f"- {c}" for c in corrections] or ["- no automatic corrections proposed"]
    md = [
        "# Reflection (ReAct)",
        "",
        "## Observe",
        *obs_lines,
        "",
        "## Evaluate",
        f"- reviewer confidence: `{reflection['evaluate'].get('reviewer_confidence')}`",
        f"- critic passed: `{reflection['evaluate'].get('critic_passed')}`",
        "",
        "## Correct",
        *corr_lines,
        "",
    ]
    (outdir / "reflection.md").write_text("\n".join(md), encoding="utf-8")

    reason = log_decision(
        state,
        "reflection",
        "Completed Observe→Evaluate→Correct",
        f"corrections={len(corrections)}; needs_human={reflection['needs_human']}",
    )
    arts = {**(state.get("artifacts") or {}), **(reason.get("artifacts") or {}), "reflection": reflection}
    return {
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [f"Reflection: {len(corrections)} correction note(s); needs_human={reflection['needs_human']}"],
    }
