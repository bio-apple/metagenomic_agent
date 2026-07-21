"""Domain RAG: tool manuals + analysis SOP / best practices."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MANUALS_PATH = ROOT / "tool_manuals.json"
SOP_PATH = ROOT / "sop_best_practices.json"


@lru_cache(maxsize=1)
def load_tool_manuals() -> list[dict[str, Any]]:
    if MANUALS_PATH.exists():
        return list(json.loads(MANUALS_PATH.read_text(encoding="utf-8")).get("tools") or [])
    return []


@lru_cache(maxsize=1)
def load_sops() -> list[dict[str, Any]]:
    if SOP_PATH.exists():
        return list(json.loads(SOP_PATH.read_text(encoding="utf-8")).get("sops") or [])
    return []


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_\-]{2,}|[\u4e00-\u9fff]+", (text or "").lower()))


def retrieve_tool_manuals(query: str, tool: str | None = None, top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve curated tool manual cards (Kraken2 / GTDB-Tk / Bakta / CheckM2 …)."""
    if tool:
        hit = [m for m in load_tool_manuals() if m.get("id") == tool.lower()]
        if hit:
            return hit
    tokens = _tokens(query)
    scored: list[dict[str, Any]] = []
    for m in load_tool_manuals():
        blob = " ".join(
            [
                m.get("id", ""),
                m.get("name", ""),
                m.get("category", ""),
                " ".join(m.get("tags") or []),
                " ".join(m.get("when_to_use") or []),
                " ".join(m.get("pitfalls") or []),
            ]
        ).lower()
        score = sum(1 for t in tokens if t in blob)
        if tool and m.get("id") == tool.lower():
            score += 10
        if score:
            scored.append({**m, "score": score})
    scored.sort(key=lambda x: -x["score"])
    if scored:
        return scored[:top_k]
    # Fallback: environment / assay defaults so Planner always gets manuals
    env = detect_sample_environment(query)
    defaults = {
        "gut": ["kraken2", "checkm2"],
        "soil": ["megahit", "checkm2", "gtdbtk"],
        "ocean": ["kraken2", "checkm2"],
        "wastewater": ["kraken2", "megahit", "checkm2", "rgi"],
        "air": ["kraken2", "diamond"],
        "skin": ["kraken2", "checkm2"],
        "mycobiome": ["kraken2", "metaphlan", "diamond"],
        "respiratory": ["kraken2", "centrifuge"],
        "general": ["kraken2", "checkm2", "gtdbtk", "bakta"],
    }.get(env, ["kraken2", "checkm2"])
    out: list[dict[str, Any]] = []
    by_id = {m.get("id"): m for m in load_tool_manuals()}
    for tid in defaults:
        if tid in by_id:
            out.append({**by_id[tid], "score": 0})
        if len(out) >= top_k:
            break
    return out[:top_k]


def retrieve_sops(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve assay / environment preprocessing SOPs."""
    tokens = _tokens(query)
    q = (query or "").lower()
    scored: list[dict[str, Any]] = []
    for sop in load_sops():
        triggers = [t.lower() for t in (sop.get("triggers") or [])]
        tag_hit = sum(1 for t in triggers if t in q)
        blob = " ".join(
            [
                sop.get("id", ""),
                sop.get("title", ""),
                " ".join(sop.get("tags") or []),
                " ".join(sop.get("steps") or []) if isinstance(sop.get("steps"), list) else "",
            ]
        ).lower()
        score = tag_hit * 3 + sum(1 for t in tokens if t in blob)
        if score:
            scored.append({**sop, "score": score})
    scored.sort(key=lambda x: -x["score"])
    if scored:
        return scored[:top_k]
    # Always surface assay selection as baseline
    base = [s for s in load_sops() if s.get("id") == "assay_16s_vs_shotgun"]
    return (base or load_sops())[:top_k]


def detect_sample_environment(query: str) -> str:
    q = (query or "").lower()
    if any(k in q for k in ("ocean", "marine", "海水", "海洋", "aquatic", "seawater")):
        return "ocean"
    if any(k in q for k in ("soil", "土壤", "rhizosphere")):
        return "soil"
    if any(k in q for k in ("wastewater", "sewage", "wwtp", "activated sludge", "污水", "废水")):
        return "wastewater"
    if any(k in q for k in ("air", "aerosol", "airborne", "atmospheric", "spore trap")):
        return "air"
    if any(k in q for k in ("skin", "dermal", "cutaneous", "皮肤")):
        return "skin"
    if any(k in q for k in ("fungi", "fungal", "mycobiome", "yeast", "真菌")):
        return "mycobiome"
    if any(k in q for k in ("respiratory", "nasopharyngeal", "bronchoalveolar", "bal ")):
        return "respiratory"
    if any(k in q for k in ("gut", "stool", "fecal", "肠道", "ibd", "obes", "host", "clinical")):
        return "gut"
    return "general"


def domain_context_block(query: str, tools: list[str] | None = None) -> str:
    """Compact text block for Planner / Tool Specialist prompts."""
    sops = retrieve_sops(query, top_k=2)
    manuals = []
    for t in tools or []:
        manuals.extend(retrieve_tool_manuals(query, tool=t, top_k=1))
    if not manuals:
        manuals = retrieve_tool_manuals(query, top_k=2)
    lines = ["# Domain RAG context", f"environment={detect_sample_environment(query)}", "", "## SOPs"]
    for s in sops:
        lines.append(f"- {s.get('id')}: {s.get('title')} (score={s.get('score')})")
        for step in (s.get("steps") or s.get("checklist") or [])[:4]:
            if isinstance(step, str):
                lines.append(f"  - {step}")
            elif isinstance(step, dict):
                lines.append(f"  - if {step.get('if')} → {step.get('choose')}")
    lines.append("")
    lines.append("## Tool manuals")
    for m in manuals:
        docs = ", ".join(d.get("url", "") for d in (m.get("docs") or [])[:2])
        lines.append(f"- {m.get('name')} ({m.get('id')}): {docs}")
        for p in (m.get("pitfalls") or [])[:2]:
            lines.append(f"  - pitfall: {p}")
    return "\n".join(lines)


def manual_citations(manuals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cites = []
    for m in manuals:
        for d in m.get("docs") or []:
            cites.append(
                {
                    "source": f"tool_manual:{m.get('id')}",
                    "url": d.get("url"),
                    "note": d.get("title") or m.get("name"),
                }
            )
    return cites
