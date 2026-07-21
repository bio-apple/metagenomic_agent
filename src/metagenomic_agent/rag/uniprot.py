"""UniProt RAG wrapper (curated + optional REST)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from metagenomic_agent.rag import retrieve


def search(query: str, top_k: int = 5, online: bool = False) -> list[dict[str, Any]]:
    local = retrieve("uniprot", query, top_k=top_k)
    if not online:
        return local
    try:
        url = "https://rest.uniprot.org/uniprotkb/search?" + urllib.parse.urlencode(
            {"query": query, "format": "json", "size": top_k}
        )
        req = urllib.request.Request(url, headers={"User-Agent": "metagenomic-agent/0.10"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        for hit in data.get("results") or []:
            acc = hit.get("primaryAccession") or ""
            name = ((hit.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName", {}).get(
                "value"
            ) or acc
            local.append(
                {
                    "database": "uniprot",
                    "id": acc,
                    "name": name,
                    "score": 0.95,
                    "source": "uniprot_rest",
                    "url": f"https://www.uniprot.org/uniprotkb/{acc}",
                }
            )
    except Exception:  # noqa: BLE001
        pass
    return local[:top_k]
