"""Literature multi-source search + Evidence Table builder."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from metagenomic_agent.rag import annotate_features, evidence_for_taxon, retrieve_multi


def pubmed_search(term: str, retmax: int = 3) -> list[dict[str, str]]:
    try:
        esearch = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
            + urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "retmax": retmax, "term": term})
        )
        with urllib.request.urlopen(esearch, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        esummary = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
            + urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(ids)})
        )
        with urllib.request.urlopen(esummary, timeout=8) as resp:
            summary = json.loads(resp.read().decode())
        results = []
        for pmid in ids:
            item = summary.get("result", {}).get(pmid, {})
            results.append(
                {
                    "pmid": pmid,
                    "title": item.get("title", ""),
                    "source": "pubmed",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
            )
        return results
    except Exception:  # noqa: BLE001
        return []


def europe_pmc_search(term: str, retmax: int = 3) -> list[dict[str, str]]:
    try:
        url = (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
            + urllib.parse.urlencode({"query": term, "format": "json", "pageSize": retmax})
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        rows = []
        for hit in (data.get("resultList") or {}).get("result") or []:
            pmid = str(hit.get("pmid") or hit.get("id") or "")
            rows.append(
                {
                    "pmid": pmid,
                    "title": hit.get("title", ""),
                    "source": "europe_pmc",
                    "url": f"https://europepmc.org/article/MED/{pmid}" if pmid else "",
                }
            )
        return rows
    except Exception:  # noqa: BLE001
        return []


def openalex_search(term: str, retmax: int = 3) -> list[dict[str, str]]:
    try:
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"search": term, "per_page": retmax, "mailto": "metagenomic-agent@example.org"}
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        rows = []
        for hit in data.get("results") or []:
            pmid = ""
            for loc in hit.get("ids") or {}:
                if "pmid" in str(loc).lower():
                    pmid = str(hit["ids"].get("pmid", "")).split("/")[-1]
            rows.append(
                {
                    "pmid": pmid or hit.get("id", "").split("/")[-1],
                    "title": hit.get("title") or hit.get("display_name") or "",
                    "source": "openalex",
                    "url": hit.get("id", ""),
                }
            )
        return rows
    except Exception:  # noqa: BLE001
        return []


def semantic_scholar_stub(term: str, retmax: int = 2) -> list[dict[str, str]]:
    """Optional Semantic Scholar; fails soft offline."""
    try:
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/search?"
            + urllib.parse.urlencode({"query": term, "limit": retmax, "fields": "title,externalIds"})
        )
        req = urllib.request.Request(url, headers={"User-Agent": "metagenomic-agent/0.6"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        rows = []
        for hit in data.get("data") or []:
            ext = hit.get("externalIds") or {}
            pmid = str(ext.get("PubMed") or "")
            rows.append(
                {
                    "pmid": pmid or hit.get("paperId", "")[:8],
                    "title": hit.get("title", ""),
                    "source": "semantic_scholar",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                }
            )
        return rows
    except Exception:  # noqa: BLE001
        return []


def collect_papers(term: str, mode: str, cfg: dict[str, Any]) -> list[dict[str, str]]:
    lit = cfg.get("literature") or {}
    if mode == "mock" or not lit.get("online", True):
        return []
    papers: list[dict[str, str]] = []
    if lit.get("pubmed", True):
        papers.extend(pubmed_search(term))
    if lit.get("europe_pmc", True):
        papers.extend(europe_pmc_search(term))
    if lit.get("openalex", False):
        papers.extend(openalex_search(term))
    if lit.get("semantic_scholar", False):
        papers.extend(semantic_scholar_stub(term))
    # dedupe by pmid/title
    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for p in papers:
        key = p.get("pmid") or p.get("title") or ""
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq[:8]


def build_evidence_table(
    genera: list[str],
    directions: dict[str, str],
    query: str,
    mode: str,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    disease = "IBD" if any(k in query.lower() for k in ("ibd", "crohn", "colitis", "炎症")) else "gut microbiome"
    rows: list[dict[str, Any]] = []
    for genus in genera:
        direction = directions.get(genus, "")
        effect = "Down" if "deplet" in direction.lower() or "decreas" in direction.lower() or "down" in direction.lower() else (
            "Up" if "enrich" in direction.lower() or "increas" in direction.lower() or "up" in direction.lower() else "Associated"
        )
        curated = evidence_for_taxon(genus, disease_hint=disease)
        bio = retrieve_multi(
            genus, dbs=["gtdb", "ncbi_taxonomy", "kegg", "uniprot", "card", "vfdb", "mgnify"], top_k_per_db=1
        )
        papers = collect_papers(f"{genus} {disease}", mode, cfg)
        if curated:
            for c in curated:
                rows.append(
                    {
                        "species": c["species"],
                        "disease": c["disease"],
                        "pmid": c["pmid"],
                        "effect": c["effect"],
                        "source": c["source"],
                        "confidence": c["confidence"],
                        "url": c.get("url", ""),
                        "bio_db_hits": {k: v for k, v in bio.items() if v},
                    }
                )
        elif papers:
            p0 = papers[0]
            rows.append(
                {
                    "species": genus,
                    "disease": disease,
                    "pmid": p0.get("pmid", ""),
                    "effect": effect,
                    "source": p0.get("source", "online"),
                    "confidence": 0.55,
                    "url": p0.get("url", ""),
                    "title": p0.get("title", ""),
                    "bio_db_hits": {k: v for k, v in bio.items() if v},
                }
            )
        else:
            rows.append(
                {
                    "species": genus,
                    "disease": disease,
                    "pmid": "kb",
                    "effect": effect or "Associated",
                    "source": "curated_fallback",
                    "confidence": 0.4,
                    "url": "",
                    "bio_db_hits": {k: v for k, v in bio.items() if v},
                }
            )
    # annotate top functional-like tokens from query
    _ = annotate_features(genera[:3])
    return rows


def evidence_table_md(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Evidence Table",
        "",
        "| Species | Disease | PMID | Effect | Source | Confidence |",
        "|---------|---------|------|--------|--------|------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('species','')} | {r.get('disease','')} | {r.get('pmid','')} | "
            f"{r.get('effect','')} | {r.get('source','')} | {r.get('confidence','')} |"
        )
    return "\n".join(lines) + "\n"
