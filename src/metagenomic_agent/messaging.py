"""Helpers for structured agent messaging."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from metagenomic_agent.state import AgentMessage


def emit(
    from_agent: str,
    to_agent: str,
    msg_type: Literal["log", "plan", "result", "warning", "hitl", "error", "metric"],
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> AgentMessage:
    return AgentMessage(
        id=str(uuid.uuid4())[:8],
        from_agent=from_agent,
        to_agent=to_agent,
        type=msg_type,
        payload=payload,
        correlation_id=correlation_id or "",
        ts=time.time(),
    )


def append_msg(state_messages: list[AgentMessage] | None, msg: AgentMessage) -> list[AgentMessage]:
    out = list(state_messages or [])
    out.append(msg)
    return out
