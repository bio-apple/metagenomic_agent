"""Per-database convenience wrappers for bio RAG."""

from __future__ import annotations

from typing import Any

from metagenomic_agent.rag import retrieve


def gtdb(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("gtdb", query, top_k=top_k)


def card(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("card", query, top_k=top_k)


def vfdb(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("vfdb", query, top_k=top_k)


def kegg(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("kegg", query, top_k=top_k)


def mgnify(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("mgnify", query, top_k=top_k)


def eggnog(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("eggnog", query, top_k=top_k)


def ncbi_taxonomy(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve("ncbi_taxonomy", query, top_k=top_k)
