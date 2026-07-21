"""Supervisor Agent — validated task planning and HITL hints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from metagenomic_agent.coordinator.env_manager import probe_environment
from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.messaging import append_msg, emit
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


class PlannedTask(BaseModel):
    name: str
    agent: str
    tools: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class PlanSchema(BaseModel):
    tasks: list[PlannedTask]


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
                "tools": ["megahit", "metaspades", "metabat2", "maxbin2", "checkm2", "gtdbtk"],
                "params": {
                    "assembler": pipe.get("default_assembler", "megahit"),
                    "binners": pipe.get("binners", ["metabat2", "maxbin2"]),
                },
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
                "tools": ["shannon", "bray_curtis", "mannwhitney_bh"],
                "params": {},
                "depends_on": ["taxonomy_profile"],
            }
        )
    tasks.extend(
        [
            {"name": "quality_critique", "agent": "Critic Agent", "tools": [], "params": {}, "depends_on": [t["name"] for t in tasks]},
            {"name": "literature_reasoning", "agent": "Literature Agent", "tools": ["pubmed", "rag"], "params": {}, "depends_on": ["quality_critique"]},
            {"name": "report_generation", "agent": "Report Agent", "tools": [], "params": {}, "depends_on": ["literature_reasoning"]},
        ]
    )
    return tasks


def _tasks_to_dag(tasks: list[TaskSpec]) -> list[DagNode]:
    nodes: list[DagNode] = []
    for t in tasks:
        agent = _normalize_agent(t["agent"])
        if agent in {"critic", "literature", "report"}:
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
    swarm_ids = {n["id"] for n in nodes}
    for n in nodes:
        n["depends_on"] = [d for d in n["depends_on"] if d in swarm_ids]
    return nodes


def _validate_tasks(raw: list[dict[str, Any]]) -> list[TaskSpec] | None:
    try:
        plan = PlanSchema.model_validate({"tasks": raw})
    except ValidationError:
        return None
    tasks: list[TaskSpec] = []
    for t in plan.tasks:
        tasks.append(
            TaskSpec(
                name=t.name,
                agent=t.agent,
                tools=t.tools,
                params=t.params,
                depends_on=t.depends_on,
                status="pending",
            )
        )
    return tasks or None


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
    resp = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are the Supervisor Agent for metagenomic research. "
                    "Plan tasks for QC, Taxonomy, Assembly, Function, Statistics, Critic, Literature, Report. "
                    "Output JSON only with key tasks."
                )
            ),
            HumanMessage(
                content=f"Query: {query}\nSamples: {json.dumps(samples, ensure_ascii=False)}\nKB:\n{kb}\n"
                'Schema: {"tasks":[{"name":"...","agent":"...","tools":[],"params":{},"depends_on":[]}]}'
            ),
        ]
    )
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    data = json.loads(match.group(0))
    return _validate_tasks(list(data.get("tasks", [])))


def plan(state: AgentState) -> dict:
    config = state["config"]
    env = probe_environment()
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

    hitl: list[str] = []
    if any(n["agent"] == "assembly" for n in dag):
        hitl.append("Confirm assembly & binning strategy (MEGAHIT vs metaSPAdes; enable CheckM2/GTDB-Tk)?")
    if any(n["agent"] == "statistics" for n in dag) and not any(s.get("group") for s in state.get("samples", [])):
        hitl.append("Statistics planned but no sample groups in metadata — provide --metadata or confirm demo_mode?")

    task_json = {"tasks": [{"name": t["name"], "agent": t["agent"]} for t in tasks]}
    (Path(state["outdir"]) / "supervisor_plan.json").write_text(
        json.dumps(task_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    amsg = emit("supervisor", "executor", "plan", {"source": source, "n_tasks": len(tasks), "plan": task_json})
    return {
        "tasks": tasks,
        "dag": dag,
        "hitl_pending": hitl,
        "artifacts": {**state.get("artifacts", {}), "env": env, "plan_source": source, "supervisor_plan": task_json},
        "messages": state.get("messages", []) + [f"Supervisor planned {len(tasks)} task(s) via {source}"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }


decompose = plan
