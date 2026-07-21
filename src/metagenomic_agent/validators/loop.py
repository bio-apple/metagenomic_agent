"""Multi-level validator loop node."""

from __future__ import annotations

from metagenomic_agent.state import AgentState, ValidationResult
from metagenomic_agent.validators.biological import validate_biological
from metagenomic_agent.validators.recovery import apply_recovery, plan_recovery
from metagenomic_agent.validators.technical import validate_technical


def validate(state: AgentState) -> dict:
    technical = validate_technical(state)
    biological = validate_biological(state)
    actions = plan_recovery(state, technical, biological) if not (technical["ok"] and biological["ok"]) else []
    passed = bool(technical["ok"] and biological["ok"])
    messages = list(state.get("messages", []))
    messages.append(f"Validation {'PASS' if passed else 'FAIL'}")
    messages.extend(technical.get("messages", []))
    messages.extend(biological.get("messages", []))

    result: ValidationResult = {
        "passed": passed,
        "technical": technical,
        "biological": biological,
        "recovery_actions": actions,
        "messages": technical.get("messages", []) + biological.get("messages", []),
    }

    updates: dict = {
        "validation": result,
        "messages": messages,
    }

    if not passed and state.get("retry_count", 0) < state.get("max_retries", 2) and actions:
        new_dag = apply_recovery(list(state.get("dag", [])), actions)
        updates["dag"] = new_dag
        updates["retry_count"] = int(state.get("retry_count", 0)) + 1
        updates["messages"] = messages + [f"Recovery actions: {actions}; retry={updates['retry_count']}"]
    return updates
