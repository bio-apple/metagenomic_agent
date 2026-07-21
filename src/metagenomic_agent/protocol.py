"""Shared LangGraph state and multi-agent message protocol."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired


class SampleMeta(TypedDict):
    sample_id: str
    r1: str
    r2: NotRequired[str | None]
    platform: str
    read_length_est: int
    paired: bool
    group: NotRequired[str | None]


class AgentMessage(TypedDict):
    """Structured inter-agent communication (AI Agent role)."""

    id: str
    from_agent: str
    to_agent: str
    type: Literal["log", "plan", "result", "warning", "hitl", "error", "metric"]
    payload: dict[str, Any]
    correlation_id: NotRequired[str]
    ts: NotRequired[float]


class TaskSpec(TypedDict):
    name: str
    agent: str
    tools: NotRequired[list[str]]
    params: NotRequired[dict[str, Any]]
    depends_on: NotRequired[list[str]]
    status: NotRequired[str]


class DagNode(TypedDict):
    id: str
    agent: str
    tools: list[str]
    params: dict[str, Any]
    depends_on: list[str]
    status: NotRequired[str]


class ValidationResult(TypedDict):
    passed: bool
    technical: dict[str, Any]
    biological: dict[str, Any]
    recovery_actions: list[str]
    messages: list[str]


class CriticResult(TypedDict):
    passed: bool
    warnings: list[str]
    recommendations: list[str]
    details: dict[str, Any]


class AgentState(TypedDict):
    user_query: str
    input_path: str
    outdir: str
    mode: Literal["mock", "local", "conda", "docker"]
    config: dict[str, Any]
    samples: list[SampleMeta]
    metadata_path: NotRequired[str | None]
    tasks: list[TaskSpec]
    dag: list[DagNode]
    artifacts: dict[str, Any]
    messages: list[str]
    agent_messages: NotRequired[list[AgentMessage]]
    validation: NotRequired[ValidationResult | None]
    critic: NotRequired[CriticResult | None]
    literature: NotRequired[dict[str, Any] | None]
    statistics: NotRequired[dict[str, Any] | None]
    retry_count: int
    max_retries: int
    hitl_pending: list[str]
    hitl_auto_confirm: bool
    hitl_resolved: NotRequired[bool]
    report_path: NotRequired[str | None]
    error: NotRequired[str | None]
    run_id: NotRequired[str | None]
