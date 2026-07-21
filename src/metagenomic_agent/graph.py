"""LangGraph assembly for Metagenomic Research Agent."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from metagenomic_agent.agents import critic_agent, literature_agent, supervisor
from metagenomic_agent.execution.executor import execute_swarm
from metagenomic_agent.input.parser import parse_input
from metagenomic_agent.report import generator as report_agent
from metagenomic_agent.state import AgentState
from metagenomic_agent.validators.loop import validate
from metagenomic_agent.validators.recovery import apply_recovery


def _route_after_critic(state: AgentState) -> Literal["execute_swarm", "literature"]:
    critic = state.get("critic") or {}
    if critic.get("passed"):
        return "literature"
    if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
        # Apply recovery to DAG and retry swarm once recommendations imply tool switch
        recs = " ".join(critic.get("recommendations") or []).lower()
        actions = []
        if "metaphlan" in recs:
            actions.append("switch_taxonomy_tool")
        if "fastp" in recs or "quality" in recs:
            actions.append("loosen_qc")
        if actions:
            return "execute_swarm"
    return "literature"


def _maybe_recover(state: AgentState) -> dict:
    """Between critic FAIL and swarm retry: bump retry + adjust DAG."""
    critic = state.get("critic") or {}
    if critic.get("passed"):
        return {}
    if int(state.get("retry_count", 0)) >= int(state.get("max_retries", 2)):
        return {}
    recs = " ".join(critic.get("recommendations") or []).lower()
    actions = []
    if "metaphlan" in recs:
        actions.append("switch_taxonomy_tool")
    if "fastp" in recs or "quality" in recs or "loosen" in recs:
        actions.append("loosen_qc")
    if not actions:
        return {"retry_count": int(state.get("retry_count", 0)) + 1}
    new_dag = apply_recovery(list(state.get("dag", [])), actions)
    return {
        "dag": new_dag,
        "retry_count": int(state.get("retry_count", 0)) + 1,
        "messages": state.get("messages", []) + [f"Critic-driven recovery: {actions}"],
    }


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("parse_input", parse_input)
    g.add_node("supervisor", supervisor.plan)
    g.add_node("execute_swarm", execute_swarm)
    g.add_node("validate", validate)
    g.add_node("critic", critic_agent.run)
    g.add_node("recover", _maybe_recover)
    g.add_node("literature", literature_agent.run)
    g.add_node("report", report_agent.run)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "supervisor")
    g.add_edge("supervisor", "execute_swarm")
    g.add_edge("execute_swarm", "validate")
    g.add_edge("validate", "critic")
    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"execute_swarm": "recover", "literature": "literature"},
    )
    g.add_edge("recover", "execute_swarm")
    g.add_edge("literature", "report")
    g.add_edge("report", END)
    return g.compile()


def run_pipeline(initial: AgentState) -> AgentState:
    app = build_graph()
    return app.invoke(initial)
