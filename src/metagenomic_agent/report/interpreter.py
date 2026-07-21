"""Grounded biology interpreter — claims require authority DB + abundance/p-value evidence."""

from __future__ import annotations

import os
from typing import Any

from metagenomic_agent.knowledge.evidence_chain import write_evidence_chains
from metagenomic_agent.rag.authority import authority_context_block


def interpret(state: dict[str, Any]) -> str:
    from metagenomic_agent.knowledge.grounded_interp import write_grounded_interp

    cfg = (state.get("config") or {}).get("interpretation") or {}
    require_grounding = cfg.get("require_grounding", True)
    require_chain = cfg.get("require_evidence_chain", True)

    report = write_evidence_chains(state)
    grounded = write_grounded_interp(state)
    lines = [
        "## Biological Interpretation (Evidence-Grounded)",
        "",
        "Strategy: only state taxa grounded in GTDB/NCBI Taxonomy; "
        "species names, p/q, and effect sizes (log2FC/LDA) must come from "
        "program-generated biomarker/LEfSe tables; "
        "do not assert PCoA/pathway claims for entities outside those tables.",
        "",
        f"- Candidate taxa: {report['n_candidates']}",
        f"- Authority-grounded: {report['n_grounded']}",
        f"- Rejected (ungrounded): {report['n_rejected_ungrounded']}",
        f"- Table-bound allowed claims: {grounded.get('n_allowed')} (require_evidence_chain={require_chain})",
        f"- Table-bound blocked: {grounded.get('n_blocked')}",
        "",
        f"- {grounded.get('pcoa_note')}",
        "",
    ]
    if report.get("rejected_taxa"):
        lines.append("### Intercepted ungrounded names")
        for t in report["rejected_taxa"]:
            lines.append(f"- `{t}` (not found in GTDB/NCBI curated index)")
        lines.append("")

    lines.append("### Evidence-chain statements")
    lines.append("")
    allowed = [c for c in report.get("claims") or [] if c.get("allowed")]
    blocked = [c for c in report.get("claims") or [] if not c.get("allowed")]
    if not allowed and not blocked:
        lines.append("_No claimable taxa (no biomarkers / top genera)._")
    for c in allowed:
        lines.append(f"- {c.get('statement')}")
    for c in blocked:
        lines.append(f"- [Blocked] {c.get('statement')}")

    lines.append("")
    lines.append(f"Full JSON/Markdown: `{report.get('path', 'evidence/claims.md')}`")
    lines.append("")
    lines.append(
        "This interpretation is not a clinical diagnosis; "
        "causal relationships require independent experimental validation."
    )

    text = "\n".join(lines)
    if not require_grounding:
        return text

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not allowed:
        return text

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        contexts = "\n\n".join(
            authority_context_block(c["taxon"]) + "\nCLAIM: " + (c.get("statement") or "")
            for c in allowed[:5]
        )
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
                        "You are a metagenomics expert. Rewrite only from the given "
                        "AUTHORITY CONTEXT and CLAIM. "
                        "Species names, p-values, q-values, and log2FC/LDA in CLAIM come "
                        "from programmatic tables — do not alter numeric values; "
                        "do not introduce taxa, pathways, or causal claims that are not "
                        "present; do not overstate disease associations. "
                        "Summarize in English (2–4 sentences)."
                    )
                ),
                HumanMessage(
                    content=(
                        f"User question: {state.get('user_query')}\n\n"
                        f"AUTHORITY CONTEXT + TABLE-BOUND CLAIMS:\n{contexts}\n\n"
                        "Provide a concise summary without adding new entities "
                        "or altering p/effect values."
                    )
                ),
            ]
        )
        extra = resp.content if isinstance(resp.content, str) else str(resp.content)
        return text + "\n\n### LLM summary (retrieval-constrained)\n" + extra
    except Exception as exc:  # noqa: BLE001
        return text + f"\n\n(LLM interpretation unavailable: {exc})"
