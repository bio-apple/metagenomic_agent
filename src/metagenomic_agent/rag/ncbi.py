"""NCBI Taxonomy RAG — curated first, optional E-utilities."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from metagenomic_agent.rag import retrieve


def search(query: str, top_k: int = 5, online: bool = False) -> list[dict[str, Any]]:
    local = retrieve("ncbi_taxonomy", query, top_k=top_k)
    if not online:
        return local
    try:
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
            + urllib.parse.urlencode({"db": "taxonomy", "retmode": "json", "retmax": top_k, "term": query})
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        ids = data.get("esearchresult", {}).get("idlist", [])
        for tid in ids:
            local.append(
                {
                    "database": "ncbi_taxonomy",
                    "id": tid,
                    "name": query,
                    "score": 0.9,
                    "source": "ncbi_eutils",
                    "url": f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={tid}",
                }
            )
    except Exception:  # noqa: BLE001
        pass
    return local[:top_k]
