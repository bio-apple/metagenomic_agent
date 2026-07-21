"""Shared LangGraph state for the metagenomic agent pipeline."""

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


class AgentState(TypedDict):
    user_query: str
    input_path: str
    outdir: str
    mode: Literal["mock", "docker"]
    config: dict[str, Any]
    samples: list[SampleMeta]
    dag: list[DagNode]
    artifacts: dict[str, Any]
    messages: list[str]
    validation: NotRequired[ValidationResult | None]
    retry_count: int
    max_retries: int
    hitl_pending: list[str]
    hitl_auto_confirm: bool
    report_path: NotRequired[str | None]
    error: NotRequired[str | None]
