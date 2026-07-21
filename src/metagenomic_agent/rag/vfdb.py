"""VFDB virulence factor RAG wrapper."""

from __future__ import annotations

from typing import Any

from metagenomic_agent.rag import retrieve


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("vfdb", query, top_k=top_k)
