"""Report agent graph node."""

from __future__ import annotations

from metagenomic_agent.report.html_report import write_report
from metagenomic_agent.state import AgentState


def report(state: AgentState) -> dict:
    paths = write_report(state)
    msg = f"Report written to {paths['html']}"
    return {
        "report_path": paths["html"],
        "artifacts": {**state.get("artifacts", {}), "report": paths},
        "messages": state.get("messages", []) + [msg],
    }
