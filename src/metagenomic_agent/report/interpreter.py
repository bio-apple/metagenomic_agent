"""LLM / template biology interpreter."""

from __future__ import annotations

import os
from typing import Any


def interpret(state: dict[str, Any]) -> str:
    tax = state.get("artifacts", {}).get("taxonomy", {})
    lines = ["## 生物学意义解读", ""]
    genera: list[str] = []
    for sid, art in tax.items():
        top = art.get("top_genera") or []
        genera.extend(top)
        lines.append(f"- 样本 **{sid}** 主要属：{', '.join(top) if top else '（无）'}")

    unique = list(dict.fromkeys(genera))
    gut = {"Bacteroides", "Faecalibacterium", "Prevotella", "Bifidobacterium", "Roseburia"}
    hits = [g for g in unique if g in gut]
    if hits:
        lines.append("")
        lines.append(
            f"检测到常见肠道标志属（{', '.join(hits)}），群落结构与人类肠道宏基因组轮廓大体一致。"
        )
    else:
        lines.append("")
        lines.append("未检测到典型肠道标志属；需结合采样部位、宿主污染与数据库覆盖率进一步核查。")

    lines.append("")
    lines.append("本解读由 MVP Report Agent 生成，临床决策请结合专业医师与实验室质控。")

    text = "\n".join(lines)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return text

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
            temperature=0.3,
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
        resp = llm.invoke(
            [
                SystemMessage(content="你是宏基因组学专家，用中文简洁解读结果，避免过度临床承诺。"),
                HumanMessage(
                    content=f"用户问题：{state.get('user_query')}\n初步摘要：\n{text}\n请补充一段临床相关性讨论。"
                ),
            ]
        )
        extra = resp.content if isinstance(resp.content, str) else str(resp.content)
        return text + "\n\n### LLM 补充\n" + extra
    except Exception as exc:  # noqa: BLE001
        return text + f"\n\n(LLM 解读不可用: {exc})"
