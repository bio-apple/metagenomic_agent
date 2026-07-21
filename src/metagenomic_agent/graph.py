"""LangGraph assembly for the metagenomic agent."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from metagenomic_agent.coordinator.decomposer import decompose
from metagenomic_agent.execution.executor import execute_swarm
from metagenomic_agent.input.parser import parse_input
from metagenomic_agent.report.agent import report
from metagenomic_agent.state import AgentState
from metagenomic_agent.validators.loop import validate


def _route_after_validate(state: AgentState) -> Literal["execute_swarm", "report"]:
    validation = state.get("validation") or {}
    if validation.get("passed"):
        return "report"
    if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)) and validation.get(
        "recovery_actions"
    ):
        return "execute_swarm"
    return "report"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("parse_input", parse_input)
    g.add_node("decompose", decompose)
    g.add_node("execute_swarm", execute_swarm)
    g.add_node("validate", validate)
    g.add_node("report", report)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "decompose")
    g.add_edge("decompose", "execute_swarm")
    g.add_edge("execute_swarm", "validate")
    g.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"execute_swarm": "execute_swarm", "report": "report"},
    )
    g.add_edge("report", END)
    return g.compile()


def run_pipeline(initial: AgentState) -> AgentState:
    app = build_graph()
    return app.invoke(initial)
