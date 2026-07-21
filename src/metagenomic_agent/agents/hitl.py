"""HITL checkpoint node — human confirmation before expensive steps."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.prompt import Confirm

from metagenomic_agent.messaging import append_msg, emit
from metagenomic_agent.state import AgentState

console = Console()


def hitl_checkpoint(state: AgentState) -> dict[str, Any]:
    pending = list(state.get("hitl_pending") or [])
    auto = bool(state.get("hitl_auto_confirm"))
    if not pending:
        return {"hitl_resolved": True, "hitl_pending": []}

    if auto:
        msg = emit(
            "hitl",
            "executor",
            "hitl",
            {"action": "auto_confirm", "items": pending},
        )
        return {
            "hitl_pending": [],
            "hitl_resolved": True,
            "messages": state.get("messages", []) + [f"HITL auto-confirmed: {len(pending)} item(s)"],
            "agent_messages": append_msg(state.get("agent_messages"), msg),
        }

    console.print("[yellow]Human-in-the-loop checkpoints:[/yellow]")
    for item in pending:
        console.print(f"  • {item}")
    ok = Confirm.ask("Proceed with planned workflow?", default=True)
    if not ok:
        msg = emit("hitl", "system", "hitl", {"action": "abort", "items": pending})
        return {
            "hitl_resolved": False,
            "error": "Aborted at HITL checkpoint",
            "messages": state.get("messages", []) + ["HITL: user aborted"],
            "agent_messages": append_msg(state.get("agent_messages"), msg),
            "dag": [],  # skip swarm
        }

    msg = emit("hitl", "executor", "hitl", {"action": "confirmed", "items": pending})
    return {
        "hitl_pending": [],
        "hitl_resolved": True,
        "messages": state.get("messages", []) + ["HITL: user confirmed"],
        "agent_messages": append_msg(state.get("agent_messages"), msg),
    }
