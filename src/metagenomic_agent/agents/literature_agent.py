"""Literature Agent — multi-source search, bio-DB RAG, and Evidence Table (grounded)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from metagenomic_agent.agents.evidence import build_evidence_table, evidence_table_md
from metagenomic_agent.knowledge import rag as micro_rag
from metagenomic_agent.knowledge.evidence_chain import write_evidence_chains
from metagenomic_agent.rag import retrieve_multi
from metagenomic_agent.rag.authority import authority_context_block, ground_taxon

MECHANISM_KB = {
    "Faecalibacterium": (
        "Faecalibacterium produces butyrate, which may influence intestinal barrier integrity "
        "and anti-inflammatory signaling in the gut mucosa."
    ),
    "Escherichia": (
        "Escherichia enrichment, especially adherent-invasive E. coli (AIEC), has been associated "
        "with mucosal inflammation in IBD cohorts."
    ),
    "Bacteroides": (
        "Bacteroides species contribute to polysaccharide degradation and immunomodulatory "
        "metabolite production in the healthy gut microbiome."
    ),
    "Prevotella": (
        "Prevotella abundance often tracks with dietary fiber patterns and may modulate "
        "mucosal immune tone."
    ),
    "Bifidobacterium": (
        "Bifidobacterium is a common early-life and probiotic-associated genus linked to "
        "SCFA production and epithelial health."
    ),
}


def _biomarker_genera(state: dict[str, Any]) -> list[str]:
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    genera = [b["genus"] for b in stats.get("biomarker_list", []) if b.get("genus")]
    if genera:
        return genera
    tops: list[str] = []
    for art in state.get("artifacts", {}).get("taxonomy", {}).values():
        tops.extend(art.get("top_genera") or [])
    for hit in micro_rag.search_kb(state.get("user_query") or "", top_k=3):
        tops.append(hit["taxon"])
    return list(dict.fromkeys(tops))[:5]


def _llm_explain(genus: str, direction: str, query: str, auth_ctx: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
            temperature=0.1,
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
        resp = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a microbiome literature expert. "
                        "ONLY paraphrase the provided AUTHORITY CONTEXT. "
                        "Do not invent taxa, pathways, or causal disease claims. "
                        "Be concise and cautious."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Query: {query}\nGenus: {genus}\nDirection: {direction}\n\n"
                        f"AUTHORITY CONTEXT:\n{auth_ctx}\n\n"
                        "Explain possible mechanisms in 2-3 sentences using only the context above."
                    )
                ),
            ]
        )
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    except Exception:  # noqa: BLE001
        return None


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"]) / "literature_summary"
    outdir.mkdir(parents=True, exist_ok=True)
    evidence_dir = Path(state["outdir"]) / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    genera = _biomarker_genera(state)
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    directions = {b["genus"]: b.get("direction", "") for b in stats.get("biomarker_list", [])}
    cfg = state.get("config") or {}
    mode = state.get("mode", "mock")
    require_grounding = (cfg.get("interpretation") or {}).get("require_grounding", True)

    entries: list[dict[str, Any]] = []
    rejected: list[str] = []
    md_lines = [
        "# Literature Summary",
        "",
        "> Anti-hallucination: taxa must resolve in GTDB/NCBI curated authority index; "
        "mechanisms are RAG-bound.",
        "",
    ]

    for genus in genera:
        ground = ground_taxon(genus)
        if require_grounding and not ground["grounded"]:
            rejected.append(genus)
            md_lines.append(f"## {genus} [REJECTED — ungrounded]")
            md_lines.append(f"- Reason: {ground.get('reason')}")
            md_lines.append("")
            continue

        direction = directions.get(genus, "")
        rag_hits = micro_rag.retrieve(genus)
        bio_hits = retrieve_multi(
            genus, dbs=["gtdb", "ncbi_taxonomy", "kegg", "uniprot", "card", "vfdb", "mgnify"], top_k_per_db=2
        )
        auth_ctx = authority_context_block(genus)
        if rag_hits:
            mechanism = rag_hits[0].get("mechanism") or MECHANISM_KB.get(genus, "")
            refs = rag_hits[0].get("references") or []
        else:
            mechanism = MECHANISM_KB.get(genus, "")
            if not mechanism and ground["grounded"]:
                notes = [h.get("notes") for h in (ground.get("hits") or []) if h.get("notes")]
                mechanism = notes[0] if notes else f"{ground.get('canonical_name')} matched in authority index."
            refs = []
        llm_extra = _llm_explain(genus, direction, state.get("user_query", ""), auth_ctx)

        from metagenomic_agent.agents.evidence import collect_papers

        papers = collect_papers(f"{genus} microbiome IBD OR gut", mode, cfg)
        if not papers:
            papers = [
                {
                    "pmid": r.get("id", "kb"),
                    "title": r.get("title", f"KB note on {genus}"),
                    "source": "gut_microbe_kb",
                    "url": "",
                }
                for r in refs
            ] or [
                {
                    "pmid": "mock",
                    "title": f"Curated note on {genus} in gut inflammation contexts",
                    "source": "internal_kb",
                    "url": "",
                }
            ]

        db_ids = [
            {"database": h.get("database"), "id": h.get("id"), "name": h.get("name")}
            for hits in bio_hits.values()
            for h in hits[:1]
            if h.get("id")
        ]
        entry = {
            "genus": genus,
            "grounded": ground["grounded"],
            "canonical_name": ground.get("canonical_name"),
            "database_ids": ground.get("database_ids") or db_ids,
            "direction": direction,
            "interpretation": mechanism,
            "llm_interpretation": llm_extra,
            "papers": papers,
            "rag": rag_hits[:2],
            "bio_db_rag": bio_hits,
            "authority_context": auth_ctx,
        }
        entries.append(entry)
        md_lines.append(f"## {genus}")
        if direction:
            md_lines.append(f"- Direction: `{direction}`")
        md_lines.append(f"- Grounded: `{ground['grounded']}` canonical=`{ground.get('canonical_name')}`")
        for d in (ground.get("database_ids") or [])[:4]:
            md_lines.append(f"- DB: {d.get('database')}:{d.get('id')}")
        md_lines.append(f"- Interpretation: {mechanism}")
        if llm_extra:
            md_lines.append(f"- LLM (RAG-constrained): {llm_extra}")
        for db, hits in bio_hits.items():
            if hits:
                md_lines.append(f"- BioDB[{db}]: {hits[0].get('name') or hits[0].get('id')}")
        for p in papers:
            md_lines.append(f"- Paper: {p.get('title')} ({p.get('pmid')}) {p.get('url', '')}")
        md_lines.append("")

    evidence_rows = build_evidence_table(
        [e["genus"] for e in entries], directions, state.get("user_query") or "", mode, cfg
    )
    (evidence_dir / "evidence_table.json").write_text(
        json.dumps(evidence_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (evidence_dir / "evidence_table.md").write_text(evidence_table_md(evidence_rows), encoding="utf-8")

    claims = write_evidence_chains({**state, "literature": {"entries": entries}})

    (outdir / "literature_summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    (outdir / "literature_summary.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    literature = {
        "entries": entries,
        "path": str(outdir / "literature_summary.md"),
        "evidence_table": str(evidence_dir / "evidence_table.md"),
        "claims_path": claims.get("path"),
        "rejected_ungrounded": rejected,
    }
    return {
        "literature": literature,
        "artifacts": {
            **state.get("artifacts", {}),
            "literature": literature,
            "evidence_table": evidence_rows,
            "evidence_table_path": str(evidence_dir / "evidence_table.json"),
            "evidence_claims": claims,
        },
        "messages": state.get("messages", [])
        + [
            f"Literature Agent: {len(entries)} grounded taxa; "
            f"rejected_ungrounded={len(rejected)}; claims={len(claims.get('claims') or [])}"
        ],
    }
