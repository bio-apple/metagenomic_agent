"""BacDive RAG wrapper (+ optional REST soft-fail)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from metagenomic_agent.rag import retrieve


def search(query: str, top_k: int = 5, online: bool = False) -> list[dict[str, Any]]:
    local = retrieve("bacdive", query, top_k=top_k)
    if not online:
        return local
    try:
        url = "https://api.bacdive.dsmz.de/taxon/" + urllib.parse.quote(query)
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "metagenomic-agent/0.7"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, dict):
            local.insert(
                0,
                {
                    "database": "bacdive",
                    "score": 1.0,
                    "name": query,
                    "remote": True,
                    "source": "bacdive_api",
                    "id": str(data.get("id") or ""),
                },
            )
    except Exception:  # noqa: BLE001
        pass
    return local[:top_k]
