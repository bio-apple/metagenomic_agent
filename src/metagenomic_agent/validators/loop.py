"""Multi-level validator — does NOT increment retry_count (self_heal owns retries)."""

from __future__ import annotations

from metagenomic_agent.state import AgentState, ValidationResult
from metagenomic_agent.validators.biological import validate_biological
from metagenomic_agent.validators.recovery import plan_recovery
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
    messages.extend([f"BIO-WARN: {w}" for w in biological.get("warnings", [])])

    result: ValidationResult = {
        "passed": passed,
        "technical": technical,
        "biological": biological,
        "recovery_actions": actions,
        "messages": technical.get("messages", []) + biological.get("messages", []),
    }
    artifacts = dict(state.get("artifacts") or {})
    artifacts["biological_warnings"] = biological.get("warnings") or []
    return {"validation": result, "messages": messages, "artifacts": artifacts}
