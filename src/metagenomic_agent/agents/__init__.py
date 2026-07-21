"""Agent registry matching developer documentation layout."""

from metagenomic_agent.agents import (
    assembly_agent,
    critic_agent,
    function_agent,
    literature_agent,
    qc_agent,
    statistics_agent,
    supervisor,
    taxonomy_agent,
    visualization_agent,
)
from metagenomic_agent.report import generator as report_agent

# Swarm agents executed by the DAG executor
AGENT_REGISTRY = {
    "qc": qc_agent.run,
    "qc_host": qc_agent.run,
    "taxonomy": taxonomy_agent.run,
    "assembly": assembly_agent.run,
    "functional": function_agent.run,
    "function": function_agent.run,
    "statistics": statistics_agent.run,
    "stats": statistics_agent.run,
    "visualization": visualization_agent.run,
}

__all__ = [
    "AGENT_REGISTRY",
    "supervisor",
    "qc_agent",
    "taxonomy_agent",
    "assembly_agent",
    "function_agent",
    "statistics_agent",
    "critic_agent",
    "literature_agent",
    "visualization_agent",
    "report_agent",
]
