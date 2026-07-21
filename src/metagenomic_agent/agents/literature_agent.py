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
        rag_mode = str((cfg.get("rag") or {}).get("mode") or "hybrid")
        bio_hits = retrieve_multi(
            genus,
            dbs=["gtdb", "ncbi_taxonomy", "kegg", "uniprot", "card", "vfdb", "mgnify"],
            top_k_per_db=2,
            mode=rag_mode,
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

    # Structured literature_report.md (Background / Findings / Evidence / Limitations / References)
    report_md = _write_literature_report(
        outdir,
        query=state.get("user_query") or "",
        entries=entries,
        evidence_rows=evidence_rows,
        rejected=rejected,
        claims=claims,
    )

    from metagenomic_agent.knowledge.reasoning_log import log_decision

    reason_patch = log_decision(
        state,
        "literature",
        f"Grounded {len(entries)} taxa; wrote literature_report.md",
        f"require_grounding={require_grounding}; rejected={len(rejected)}",
        n_entries=len(entries),
    )

    literature = {
        "entries": entries,
        "path": str(outdir / "literature_summary.md"),
        "report_path": report_md,
        "evidence_table": str(evidence_dir / "evidence_table.md"),
        "claims_path": claims.get("path"),
        "rejected_ungrounded": rejected,
    }
    arts = {
        **state.get("artifacts", {}),
        **(reason_patch.get("artifacts") or {}),
        "literature": literature,
        "evidence_table": evidence_rows,
        "evidence_table_path": str(evidence_dir / "evidence_table.json"),
        "evidence_claims": claims,
        "literature_report": report_md,
    }
    return {
        "literature": literature,
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [
            f"Literature Agent: {len(entries)} grounded taxa; "
            f"rejected_ungrounded={len(rejected)}; claims={len(claims.get('claims') or [])}; "
            f"report={report_md}"
        ],
    }


def _write_literature_report(
    outdir: Path,
    *,
    query: str,
    entries: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    rejected: list[str],
    claims: dict[str, Any],
) -> str:
    lines = [
        "# Literature Report",
        "",
        "## Background",
        "",
        f"Research question: {query or '(unspecified)'}",
        "",
        "This report aggregates PubMed/Europe PMC (when online), curated bio-DB RAG "
        "(GTDB/KEGG/CARD/VFDB), and table-bound biomarker directions. "
        "Ungrounded taxa are excluded from Key Findings.",
        "",
        "## Key Findings",
        "",
    ]
    if not entries:
        lines.append("- No grounded taxa with literature context in this run.")
    for e in entries:
        lines.append(
            f"- **{e.get('canonical_name') or e.get('genus')}** "
            f"({e.get('direction') or 'n/a'}): {e.get('interpretation') or 'see papers'}"
        )
    lines.extend(["", "## Supporting Evidence", ""])
    for row in (evidence_rows or [])[:15]:
        lines.append(
            f"- {row.get('species')}: {row.get('effect')} in {row.get('disease')} "
            f"(PMID {row.get('pmid')}, source={row.get('source')})"
        )
    if not evidence_rows:
        for e in entries:
            for p in (e.get("papers") or [])[:2]:
                lines.append(f"- {e.get('genus')}: {p.get('title')} ({p.get('pmid')})")
    n_claims = len((claims or {}).get("claims") or [])
    lines.extend(
        [
            "",
            f"Evidence claims written: {n_claims} (see `evidence/claims.md`).",
            "",
            "## Limitations",
            "",
            "- Automated retrieval is not a systematic review; PMIDs need expert triage.",
            "- Curated RAG indices may be stubs until full local dumps are mounted under `database/`.",
            f"- Rejected ungrounded taxa: {', '.join(rejected) if rejected else 'none'}.",
            "- LLM paraphrases (if any) are constrained to authority context only.",
            "",
            "## References",
            "",
        ]
    )
    seen: set[str] = set()
    for row in evidence_rows or []:
        pmid = str(row.get("pmid") or "")
        if pmid and pmid not in seen and pmid not in {"kb", "mock"}:
            seen.add(pmid)
            lines.append(f"- PMID {pmid}: {row.get('species')} — {row.get('url') or ''}")
    for e in entries:
        for p in e.get("papers") or []:
            pmid = str(p.get("pmid") or "")
            if pmid and pmid not in seen:
                seen.add(pmid)
                lines.append(f"- {pmid}: {p.get('title')} {p.get('url') or ''}")
    if len(seen) == 0:
        lines.append("- (no external PMIDs; see internal KB notes in literature_summary.json)")

    path = outdir / "literature_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    # Also top-level convenience path
    top = outdir.parent / "literature_report.md"
    top.write_text("\n".join(lines), encoding="utf-8")
    return str(top)
