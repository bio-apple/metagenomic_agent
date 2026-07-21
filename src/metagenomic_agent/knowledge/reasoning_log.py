"""Unified cross-agent reasoning / decision audit trail under outdir/reasoning/."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def reasoning_dir(outdir: str | Path) -> Path:
    d = Path(outdir) / "reasoning"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_decision(
    state: dict[str, Any],
    *,
    agent: str,
    decision: str,
    reason: str,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one auditable decision step; returns artifact patch fragment."""
    outdir = state.get("outdir")
    if not outdir:
        return {}
    root = reasoning_dir(outdir)
    chain_path = root / "chain.jsonl"
    arts = dict(state.get("artifacts") or {})
    steps = list(arts.get("reasoning_steps") or [])
    step_n = len(steps) + 1
    record = {
        "step": step_n,
        "agent": agent,
        "decision": decision,
        "reason": reason,
        "ts": time.time(),
        "run_id": state.get("run_id"),
        **(extras or {}),
    }
    steps.append(record)
    with chain_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    arts["reasoning_steps"] = steps
    arts["reasoning_path"] = str(chain_path)
    return {"artifacts": arts}


def finalize_reasoning(state: dict[str, Any]) -> dict[str, Any]:
    """Write chain.json + human-readable chain.md."""
    outdir = state.get("outdir")
    if not outdir:
        return {}
    root = reasoning_dir(outdir)
    arts = dict(state.get("artifacts") or {})
    steps = list(arts.get("reasoning_steps") or [])
    # Reload from jsonl if in-memory empty (resume)
    chain_path = root / "chain.jsonl"
    if not steps and chain_path.exists():
        for line in chain_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                steps.append(json.loads(line))
    (root / "chain.json").write_text(json.dumps(steps, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Reasoning chain", "", f"run_id: `{state.get('run_id')}`", ""]
    for s in steps:
        md.append(f"## Step {s.get('step')}: `{s.get('agent')}`")
        md.append(f"- **Decision:** {s.get('decision')}")
        md.append(f"- **Reason:** {s.get('reason')}")
        md.append("")
    (root / "chain.md").write_text("\n".join(md), encoding="utf-8")
    arts["reasoning_steps"] = steps
    arts["reasoning_md"] = str(root / "chain.md")
    arts["reasoning_json"] = str(root / "chain.json")
    return {"artifacts": arts}


def log_decision(
    state: dict[str, Any],
    agent: str,
    decision: str,
    reason: str,
    **extras: Any,
) -> dict[str, Any]:
    """Convenience: merge append into state-like patch."""
    return append_decision(state, agent=agent, decision=decision, reason=reason, extras=extras or None)
