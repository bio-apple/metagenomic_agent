"""Planner Agent — parse experimental design into an end-to-end analysis pipeline.

Composes Router + Bio Reasoning + Supervisor outputs into a single Planner artifact
consumed by Executor / QC-Critic / Reporter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.domain_rag import (
    detect_sample_environment,
    domain_context_block,
    retrieve_sops,
    retrieve_tool_manuals,
)
from metagenomic_agent.messaging import append_msg, emit


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    arts = dict(state.get("artifacts") or {})
    bio = arts.get("bio_reasoning") or {}
    router = arts.get("router") or {}
    specialist = arts.get("tool_specialist") or {}
    query = state.get("user_query") or ""
    env = detect_sample_environment(query)
    sops = retrieve_sops(query, top_k=3)
    tools = []
    for n in state.get("dag") or []:
        tools.extend(n.get("tools") or [])
    tools = list(dict.fromkeys(tools))
    manuals = retrieve_tool_manuals(query, top_k=4)
    for t in ("kraken2", "gtdbtk", "bakta", "checkm2"):
        if t in tools or t in {s.get("tool") for s in (specialist.get("specialists") or [])}:
            manuals = retrieve_tool_manuals(query, tool=t, top_k=1) + manuals
    # dedupe manuals by id
    seen = set()
    uniq_manuals = []
    for m in manuals:
        mid = m.get("id")
        if mid in seen:
            continue
        seen.add(mid)
        uniq_manuals.append(m)

    pipeline = list(bio.get("pipeline_steps") or [])
    if not pipeline:
        pipeline = [n.get("agent") for n in (state.get("dag") or []) if n.get("status") != "skipped"]

    plan = {
        "role": "planner",
        "query": query,
        "sample_environment": env,
        "study_goal": bio.get("study_goal") or router.get("primary_intent"),
        "recommended_assay": bio.get("recommended_assay"),
        "assay_note": bio.get("assay_note"),
        "pipeline_steps": pipeline,
        "dag_agents": [n.get("agent") for n in (state.get("dag") or [])],
        "tools": tools,
        "enable": {
            "host_filter": bio.get("enable_host_filter"),
            "function": bio.get("enable_function"),
            "statistics": bio.get("enable_statistics"),
            "assembly": bio.get("enable_assembly"),
        },
        "assembler": bio.get("assembler_preference"),
        "sops": [{"id": s.get("id"), "title": s.get("title"), "score": s.get("score")} for s in sops],
        "tool_manuals": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "docs": m.get("docs"),
                "key_params": m.get("key_params"),
                "pitfalls": (m.get("pitfalls") or [])[:3],
            }
            for m in uniq_manuals[:6]
        ],
        "domain_context": domain_context_block(query, tools=tools[:8]),
        "policy": "planner_emits_pipeline_executor_runs_params_not_freeform_shell",
    }

    out = Path(state["outdir"]) / "planner"
    out.mkdir(parents=True, exist_ok=True)
    (out / "planner_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [
        "# Planner Agent — Analysis Pipeline",
        "",
        f"- Environment: `{env}`",
        f"- Assay: `{plan.get('recommended_assay')}`",
        f"- Goal: `{plan.get('study_goal')}`",
        "",
        "## Pipeline",
        *[f"{i+1}. {s}" for i, s in enumerate(pipeline)],
        "",
        "## SOPs",
        *[f"- {s['id']}: {s['title']}" for s in plan["sops"]],
        "",
        "## Tool manuals indexed",
        *[f"- {m['name']} — {(m.get('docs') or [{}])[0].get('url', '')}" for m in plan["tool_manuals"]],
        "",
        "## Domain context",
        "```",
        plan["domain_context"][:2000],
        "```",
        "",
    ]
    (out / "planner_plan.md").write_text("\n".join(md), encoding="utf-8")

    amsg = emit("planner", "executor", "plan", {"env": env, "n_steps": len(pipeline)})
    arts["planner"] = {**plan, "path": str(out / "planner_plan.json")}
    return {
        "artifacts": arts,
        "messages": state.get("messages", []) + [f"Planner: {env} / {plan.get('recommended_assay')} / {len(pipeline)} steps"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }
