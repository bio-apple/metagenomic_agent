"""Router Agent — understand intent and dispatch to specialist pathways."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.domain_kb import infer_domains, recommend_tools
from metagenomic_agent.messaging import append_msg, emit


INTENT_LABELS = (
    "taxonomy_profiling",
    "mag_recovery",
    "functional_annotation",
    "biomarker_discovery",
    "virus_analysis",
    "qc_only",
    "literature_qa",
)


def _classify_intent(query: str) -> dict[str, Any]:
    q = (query or "").lower()
    scores = {k: 0.0 for k in INTENT_LABELS}
    rules = [
        (("qc", "quality", "fastp", "质控"), "qc_only", 1.0),
        (("virus", "phage", "virome", "病毒", "噬菌体"), "virus_analysis", 1.2),
        (("mag", "assembl", "bin", "分箱", "组装"), "mag_recovery", 1.1),
        (("function", "kegg", "pathway", "功能", "humann"), "functional_annotation", 1.0),
        (("biomarker", "differential", "标志", "差异", "ibd"), "biomarker_discovery", 1.2),
        (("literature", "paper", "pubmed", "文献"), "literature_qa", 0.9),
        (("taxon", "species", "kraken", "metaphlan", "物种", "分类"), "taxonomy_profiling", 1.0),
    ]
    for keys, label, w in rules:
        if any(k in q for k in keys):
            scores[label] += w
    if max(scores.values()) == 0:
        scores["taxonomy_profiling"] = 0.5
        scores["biomarker_discovery"] = 0.3
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    primary = ranked[0][0]
    secondary = [k for k, v in ranked[1:4] if v > 0]
    return {"primary_intent": primary, "secondary_intents": secondary, "scores": scores}


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    query = state.get("user_query") or ""
    samples = state.get("samples") or []
    read_lengths = [float(s.get("read_length_est") or 150) for s in samples] or [150.0]
    ctx = {
        "n_samples": len(samples),
        "read_length": max(read_lengths),
        "memory_gb": ((state.get("config") or {}).get("linux") or {}).get("memory_gb", 32),
    }
    intent = _classify_intent(query)
    domains = infer_domains(query)
    tools = recommend_tools(query, ctx)

    # Dispatch map: which specialist lanes to activate
    dispatch = {
        "tool_specialist": True,
        "plan_validator": True,
        "workflow_generator": intent["primary_intent"] in {"mag_recovery", "taxonomy_profiling", "virus_analysis"},
        "literature": intent["primary_intent"] in {"biomarker_discovery", "literature_qa"}
        or "biomarker_discovery" in intent["secondary_intents"],
        "statistics": intent["primary_intent"] == "biomarker_discovery"
        or "biomarker_discovery" in intent["secondary_intents"],
    }

    route = {
        "intent": intent,
        "domains": domains,
        "recommended_tools": [{"tool": t["tool"], "strengths": t.get("strengths"), "status": t.get("status")} for t in tools],
        "dispatch": dispatch,
        "context": ctx,
    }

    outdir = Path(state["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "router_decision.json").write_text(json.dumps(route, indent=2, ensure_ascii=False), encoding="utf-8")

    amsg = emit("router", "supervisor", "plan", route)
    return {
        "artifacts": {**state.get("artifacts", {}), "router": route},
        "messages": state.get("messages", [])
        + [f"Router Agent: intent={intent['primary_intent']}, domains={domains}, tools={[t['tool'] for t in tools[:5]]}"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }
