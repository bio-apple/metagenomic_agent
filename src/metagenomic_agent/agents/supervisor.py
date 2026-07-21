"""Supervisor Agent — task planning and coordination."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from metagenomic_agent.coordinator.env_manager import probe_environment
from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.state import AgentState, DagNode, TaskSpec

KB_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "best_practices.md"

AGENT_ALIASES = {
    "qc agent": "qc",
    "qc": "qc",
    "quality_control": "qc",
    "taxonomy agent": "taxonomy",
    "taxonomy": "taxonomy",
    "taxonomy_profile": "taxonomy",
    "assembly agent": "assembly",
    "assembly": "assembly",
    "function agent": "function",
    "functional": "function",
    "function": "function",
    "statistics agent": "statistics",
    "statistics": "statistics",
    "stats": "statistics",
    "critic agent": "critic",
    "critic": "critic",
    "literature agent": "literature",
    "literature": "literature",
    "report agent": "report",
    "report": "report",
}


def _normalize_agent(name: str) -> str:
    return AGENT_ALIASES.get(name.strip().lower(), name.strip().lower())


def _default_plan(query: str, config: dict[str, Any]) -> list[TaskSpec]:
    q = query.lower()
    wants_biomarker = any(k in q for k in ("biomarker", "标志", "差异", "ibd", "disease", "对照", "control"))
    wants_assembly = any(k in q for k in ("mag", "assembly", "组装", "分箱", "bin"))
    wants_function = any(k in q for k in ("function", "pathway", "功能", "kegg", "resistance", "耐药"))
    pipe = config.get("pipeline", {})

    tasks: list[TaskSpec] = [
        {"name": "quality_control", "agent": "QC Agent", "tools": ["fastp", "filter_host"], "params": {}, "depends_on": []},
        {
            "name": "taxonomy_profile",
            "agent": "Taxonomy Agent",
            "tools": list(pipe.get("taxonomy_tools", ["kraken2", "metaphlan"])),
            "params": {"confidence": 0.05},
            "depends_on": ["quality_control"],
        },
    ]
    if wants_assembly or pipe.get("enable_assembly", False):
        tasks.append(
            {
                "name": "assembly_binning",
                "agent": "Assembly Agent",
                "tools": ["megahit", "metabat2", "gtdbtk"],
                "params": {},
                "depends_on": ["quality_control"],
            }
        )
    if wants_function or pipe.get("enable_functional", True):
        tasks.append(
            {
                "name": "functional_annotation",
                "agent": "Function Agent",
                "tools": ["diamond", "eggnog"],
                "params": {},
                "depends_on": ["quality_control"],
            }
        )
    if wants_biomarker or pipe.get("enable_statistics", True):
        tasks.append(
            {
                "name": "statistical_analysis",
                "agent": "Statistics Agent",
                "tools": ["vegan", "ancombc"],
                "params": {},
                "depends_on": ["taxonomy_profile"],
            }
        )
    tasks.extend(
        [
            {
                "name": "quality_critique",
                "agent": "Critic Agent",
                "tools": [],
                "params": {},
                "depends_on": [t["name"] for t in tasks],
            },
            {
                "name": "literature_reasoning",
                "agent": "Literature Agent",
                "tools": ["pubmed"],
                "params": {},
                "depends_on": ["quality_critique"],
            },
            {
                "name": "report_generation",
                "agent": "Report Agent",
                "tools": [],
                "params": {},
                "depends_on": ["literature_reasoning"],
            },
        ]
    )
    return tasks


def _tasks_to_dag(tasks: list[TaskSpec]) -> list[DagNode]:
    nodes: list[DagNode] = []
    for t in tasks:
        agent = _normalize_agent(t["agent"])
        if agent in {"critic", "literature", "report"}:
            # handled as dedicated graph nodes after swarm
            continue
        nodes.append(
            DagNode(
                id=t["name"],
                agent=agent if agent != "function" else "functional",
                tools=list(t.get("tools") or []),
                params=dict(t.get("params") or {}),
                depends_on=list(t.get("depends_on") or []),
                status="pending",
            )
        )
    # fix depends_on to only reference swarm nodes
    swarm_ids = {n["id"] for n in nodes}
    for n in nodes:
        n["depends_on"] = [d for d in n["depends_on"] if d in swarm_ids]
    return nodes


def _llm_plan(query: str, samples: list[dict], config: dict[str, Any]) -> list[TaskSpec] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    llm_cfg = config.get("llm", {})
    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", llm_cfg.get("model", "deepseek-chat")),
        temperature=llm_cfg.get("temperature", 0.2),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    kb = KB_PATH.read_text(encoding="utf-8")[:2500] if KB_PATH.exists() else ""
    schema = {
        "tasks": [
            {
                "name": "quality_control",
                "agent": "QC Agent",
                "tools": ["fastp"],
                "params": {},
                "depends_on": [],
            }
        ]
    }
    resp = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are the Supervisor Agent for metagenomic research. "
                    "Plan tasks for QC, Taxonomy, Assembly, Function, Statistics, Critic, Literature, Report. "
                    "Output JSON only."
                )
            ),
            HumanMessage(
                content=f"Query: {query}\nSamples: {json.dumps(samples, ensure_ascii=False)}\nKB:\n{kb}\n"
                f"Schema: {json.dumps(schema)}"
            ),
        ]
    )
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    data = json.loads(match.group(0))
    tasks: list[TaskSpec] = []
    for t in data.get("tasks", []):
        tasks.append(
            TaskSpec(
                name=t["name"],
                agent=t["agent"],
                tools=list(t.get("tools", [])),
                params=dict(t.get("params", {})),
                depends_on=list(t.get("depends_on", [])),
                status="pending",
            )
        )
    return tasks or None


def plan(state: AgentState) -> dict:
    """Supervisor entry: decompose scientific question into executable tasks."""
    config = state["config"]
    env = probe_environment(config.get("docker", {}).get("image", "meta:latest"))
    memory = ContextMemory(Path(state["outdir"]) / "context")
    memory.update(samples=state.get("samples", []), env=env)

    tasks = _llm_plan(state["user_query"], state.get("samples", []), config)
    source = "llm"
    if tasks is None:
        tasks = _default_plan(state["user_query"], config)
        source = "heuristic"

    dag = _tasks_to_dag(tasks)
    memory.update(tasks=tasks, dag=dag)
    memory.append_history(f"supervisor_plan:{source}:{len(tasks)}")

    # Document-format task JSON for transparency
    task_json = {"tasks": [{"name": t["name"], "agent": t["agent"]} for t in tasks]}
    (Path(state["outdir"]) / "supervisor_plan.json").write_text(
        json.dumps(task_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "tasks": tasks,
        "dag": dag,
        "artifacts": {**state.get("artifacts", {}), "env": env, "plan_source": source, "supervisor_plan": task_json},
        "messages": state.get("messages", []) + [f"Supervisor planned {len(tasks)} task(s) via {source}"],
    }


# Backward-compatible alias used by older graph wiring
decompose = plan
