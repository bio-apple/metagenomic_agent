"""Domain tool knowledge base + scientific tool routing helpers."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

KB_PATH = Path(__file__).resolve().parent / "tool_domain_kb.json"


@lru_cache(maxsize=1)
def load_tool_domain_kb() -> dict[str, Any]:
    if KB_PATH.exists():
        return json.loads(KB_PATH.read_text(encoding="utf-8"))
    return {"domains": {}, "tools": {}, "constraints": {}}


def infer_domains(query: str) -> list[str]:
    q = (query or "").lower()
    hits: list[str] = []
    mapping = [
        (("virus", "phage", "viral", "virome", "噬菌体", "病毒"), "virus"),
        (("fungi", "fungal", "真菌"), "fungi"),
        (("amr", "resistance", "card", "virulence", "耐药", "毒力"), "amr_virulence"),
        (("mag", "assembly", "binning", "分箱", "组装"), "mag_recovery"),
        (("prokaryot", "bacteria", "gut", "ibd", "taxon", "species", "细菌", "肠道"), "prokaryote_taxonomy"),
    ]
    for keys, domain in mapping:
        if any(k in q for k in keys):
            hits.append(domain)
    return list(dict.fromkeys(hits)) or ["prokaryote_taxonomy"]


def recommend_tools(query: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    kb = load_tool_domain_kb()
    domains = infer_domains(query)
    ctx = context or {}
    read_length = float(ctx.get("read_length") or 150)
    preferred: list[str] = []
    for d in domains:
        preferred.extend((kb.get("domains") or {}).get(d, {}).get("preferred") or [])
    if read_length >= 5000:
        preferred = ["microcafe"] + preferred
    names = list(dict.fromkeys(preferred))
    tools = kb.get("tools") or {}
    out = []
    for name in names:
        meta = tools.get(name) or {"specialty": [], "strengths": [], "status": "unknown"}
        out.append({"tool": name, "domains": domains, **meta})
    return out


def missing_domain_constraints(state: dict[str, Any]) -> list[str]:
    """Safety-first: ask when required scientific metadata is missing."""
    kb = load_tool_domain_kb()
    constraints = kb.get("constraints") or {}
    ask = list(constraints.get("ask_when_missing") or [])
    cfg = state.get("config") or {}
    project = {**(cfg.get("project") or {}), **((state.get("artifacts") or {}).get("project_profile") or {})}
    query = (state.get("user_query") or "").lower()
    missing: list[str] = []

    pipe = cfg.get("pipeline") or {}
    if pipe.get("enable_host_filter", True) and constraints.get("require_host_genome_version_for_host_filter"):
        if not (project.get("host_genome_version") or (cfg.get("paths") or {}).get("host_genome_version")):
            if not (cfg.get("paths") or {}).get("host_index"):
                if state.get("mode") != "mock":
                    missing.append(
                        "Host filtering enabled but host genome version / Bowtie2 index not specified "
                        "(e.g. GRCh38). Provide paths.host_index or project.host_genome_version."
                    )

    if any(k in query for k in ("interval", "bed", "vcf", "坐标", "0-based", "1-based")):
        if not project.get("coordinate_system"):
            missing.append(
                "Interval/variant analysis mentioned but coordinate system not specified (0-based vs 1-based). "
                "Set project.coordinate_system before proceeding."
            )

    if any(k in query for k in ("biomarker", "differential", "标志", "差异", "ibd")):
        samples = state.get("samples") or []
        has_groups = any(s.get("group") for s in samples)
        demo = bool((cfg.get("statistics") or {}).get("demo_mode"))
        if not has_groups and not demo and state.get("mode") != "mock":
            missing.append(
                "Differential / biomarker analysis requested but sample groups missing. "
                "Provide --metadata with sample_id,group or set statistics.demo_mode."
            )

    if "target_domain" in ask and not project.get("target_domain"):
        domains = infer_domains(state.get("user_query") or "")
        if len(domains) > 1 and "virus" in domains and "prokaryote_taxonomy" in domains:
            missing.append(
                "Query spans viral and prokaryotic analyses. Confirm project.target_domain "
                "(virus | prokaryote_taxonomy | both) to avoid incorrect tool routing."
            )

    return missing


def tool_command(tool: str, params: dict[str, Any]) -> str | None:
    meta = (load_tool_domain_kb().get("tools") or {}).get(tool) or {}
    tpl = meta.get("command_template")
    if not tpl:
        return None
    defaults = dict(meta.get("defaults") or {})
    defaults.update({k: v for k, v in params.items() if v is not None})
    keys = set(re.findall(r"\{(\w+)\}", tpl))
    for k in keys:
        defaults.setdefault(k, f"<{k}>")
    try:
        return tpl.format(**defaults)
    except Exception:  # noqa: BLE001
        return tpl
