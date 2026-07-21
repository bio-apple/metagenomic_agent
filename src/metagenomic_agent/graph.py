"""LangGraph assembly with Validator + Self-Heal loop."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from metagenomic_agent.agents import critic_agent, literature_agent, supervisor
from metagenomic_agent.execution.executor import execute_swarm
from metagenomic_agent.execution.self_heal import apply_self_heal, classify_from_errors, deep_merge_config
from metagenomic_agent.input.parser import parse_input
from metagenomic_agent.report import generator as report_agent
from metagenomic_agent.state import AgentState
from metagenomic_agent.validators.loop import validate
from metagenomic_agent.validators.recovery import apply_recovery, plan_recovery


def _route_after_validate(state: AgentState) -> Literal["self_heal", "critic"]:
    validation = state.get("validation") or {}
    errors = state.get("artifacts", {}).get("errors") or []
    if (not validation.get("passed")) or errors:
        if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
            return "self_heal"
    return "critic"


def _route_after_critic(state: AgentState) -> Literal["self_heal", "literature"]:
    critic = state.get("critic") or {}
    if critic.get("passed"):
        return "literature"
    if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
        recs = " ".join(critic.get("recommendations") or []).lower()
        if any(k in recs for k in ("metaphlan", "fastp", "quality", "assembler", "memory", "oom")):
            return "self_heal"
    return "literature"


def _self_heal(state: AgentState) -> dict:
    """Intermediate Logic Correction / Retry (architecture Validator Loop)."""
    actions: list[str] = []
    errors = list(state.get("artifacts", {}).get("errors") or [])
    actions.extend(classify_from_errors(errors))

    validation = state.get("validation") or {}
    if validation and not validation.get("passed"):
        actions.extend(
            plan_recovery(state, validation.get("technical") or {}, validation.get("biological") or {})
        )

    critic = state.get("critic") or {}
    recs = " ".join(critic.get("recommendations") or []).lower()
    if "metaphlan" in recs:
        actions.append("switch_taxonomy_tool")
    if "fastp" in recs or "quality" in recs:
        actions.append("loosen_qc")
    if "assembler" in recs or "megahit" in recs:
        actions.append("downgrade_assembler")

    actions = list(dict.fromkeys(actions))
    new_dag, cfg_patch = apply_self_heal(list(state.get("dag", [])), actions, state.get("config"))
    # Also apply legacy recovery for taxonomy confidence etc.
    new_dag = apply_recovery(new_dag, actions)
    new_config = deep_merge_config(dict(state.get("config") or {}), cfg_patch)

    # Clear prior errors for next attempt
    artifacts = dict(state.get("artifacts") or {})
    artifacts["errors"] = []
    artifacts["self_heal_actions"] = actions

    return {
        "dag": new_dag,
        "config": new_config,
        "artifacts": artifacts,
        "retry_count": int(state.get("retry_count", 0)) + 1,
        "messages": state.get("messages", [])
        + [f"Self-heal actions: {actions or ['retry']}; retry={int(state.get('retry_count', 0)) + 1}"],
    }


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("parse_input", parse_input)
    g.add_node("supervisor", supervisor.plan)
    g.add_node("execute_swarm", execute_swarm)
    g.add_node("validate", validate)
    g.add_node("self_heal", _self_heal)
    g.add_node("critic", critic_agent.run)
    g.add_node("literature", literature_agent.run)
    g.add_node("report", report_agent.run)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "supervisor")
    g.add_edge("supervisor", "execute_swarm")
    g.add_edge("execute_swarm", "validate")
    g.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"self_heal": "self_heal", "critic": "critic"},
    )
    g.add_edge("self_heal", "execute_swarm")
    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"self_heal": "self_heal", "literature": "literature"},
    )
    g.add_edge("literature", "report")
    g.add_edge("report", END)
    return g.compile()


def run_pipeline(initial: AgentState) -> AgentState:
    app = build_graph()
    return app.invoke(initial)
