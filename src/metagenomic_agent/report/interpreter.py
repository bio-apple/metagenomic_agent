"""Grounded biology interpreter — claims require authority DB + abundance/p-value evidence."""

from __future__ import annotations

import os
from typing import Any

from metagenomic_agent.knowledge.evidence_chain import write_evidence_chains
from metagenomic_agent.rag.authority import authority_context_block


def interpret(state: dict[str, Any]) -> str:
    cfg = (state.get("config") or {}).get("interpretation") or {}
    require_grounding = cfg.get("require_grounding", True)

    report = write_evidence_chains(state)
    lines = [
        "## 生物学意义解读（证据锚定）",
        "",
        "策略：仅陈述已在 GTDB/NCBI Taxonomy 锚定的分类单元；"
        "每条允许的陈述附带测定丰度、显著性（若有）及数据库 ID / PMID。",
        "",
        f"- 候选分类单元: {report['n_candidates']}",
        f"- 权威库锚定: {report['n_grounded']}",
        f"- 拒绝（未锚定）: {report['n_rejected_ungrounded']}",
        "",
    ]
    if report.get("rejected_taxa"):
        lines.append("### 已拦截的未锚定名称")
        for t in report["rejected_taxa"]:
            lines.append(f"- `{t}`（未在 GTDB/NCBI 策展索引中命中）")
        lines.append("")

    lines.append("### 证据链陈述")
    lines.append("")
    allowed = [c for c in report.get("claims") or [] if c.get("allowed")]
    blocked = [c for c in report.get("claims") or [] if not c.get("allowed")]
    if not allowed and not blocked:
        lines.append("_无可陈述的分类单元（无 biomarker / top genera）。_")
    for c in allowed:
        lines.append(f"- {c.get('statement')}")
    for c in blocked:
        lines.append(f"- [阻断] {c.get('statement')}")

    lines.append("")
    lines.append(f"完整 JSON/Markdown：`{report.get('path', 'evidence/claims.md')}`")
    lines.append("")
    lines.append("本解读不构成临床诊断；因果关系需独立实验验证。")

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
                        "你是宏基因组学专家。只能基于给定 AUTHORITY CONTEXT 与 CLAIM 进行改写，"
                        "禁止引入未出现的菌种名、通路或因果断言；不得夸大疾病关联。"
                        "用中文 2–4 句总结。"
                    )
                ),
                HumanMessage(
                    content=(
                        f"用户问题：{state.get('user_query')}\n\n"
                        f"AUTHORITY CONTEXT + CLAIMS:\n{contexts}\n\n"
                        "请在不添加新实体的前提下做简洁综述。"
                    )
                ),
            ]
        )
        extra = resp.content if isinstance(resp.content, str) else str(resp.content)
        return text + "\n\n### LLM 综述（受检索约束）\n" + extra
    except Exception as exc:  # noqa: BLE001
        return text + f"\n\n(LLM 解读不可用: {exc})"
