"""Shared LangGraph state — re-exports protocol types for compatibility."""

from __future__ import annotations

from metagenomic_agent.protocol import (  # noqa: F401
    AgentMessage,
    AgentState,
    CriticResult,
    DagNode,
    SampleMeta,
    TaskSpec,
    ValidationResult,
)
