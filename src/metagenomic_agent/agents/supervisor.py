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
from metagenomic_agent.skills.decision import decide_taxonomy_tools
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
    "resistance agent": "resistance",
    "resistance": "resistance",
    "virulence agent": "resistance",
    "resistance_virulence": "resistance",
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


def _default_plan(
    query: str, config: dict[str, Any], bio: dict[str, Any] | None = None
) -> list[TaskSpec]:
    q = query.lower()
    bio = bio or {}
    wants_biomarker = any(k in q for k in ("biomarker", "标志", "差异", "ibd", "disease", "对照", "control"))
    wants_assembly = any(k in q for k in ("mag", "assembly", "组装", "分箱", "bin"))
    pipe = config.get("pipeline", {})
    wants_function = any(k in q for k in ("function", "pathway", "功能", "kegg", "resistance", "耐药"))
    wants_resistance = any(
        k in q for k in ("resistance", "arg", "amr", "virulence", "耐药", "毒力", "card", "vfdb")
    ) or bool(pipe.get("enable_arg") or pipe.get("enable_resistance"))

    # Biological Reasoning Layer overrides / strengthens heuristics
    if bio.get("enable_statistics"):
        wants_biomarker = True
    if bio.get("enable_assembly"):
        wants_assembly = True
    if bio.get("enable_function"):
        wants_function = True
    if bio.get("study_goal") == "taxonomy_only":
        wants_function = False
        wants_biomarker = False
        wants_resistance = False

    tax_tools = list(pipe.get("taxonomy_tools") or []) or decide_taxonomy_tools(
        {
            "query": query,
            "memory_gb": (config.get("linux") or {}).get("memory_gb", 32),
            "n_samples": int(config.get("_n_samples") or 1),
            "read_length": float(config.get("_read_length") or 150),
            "prefer_accuracy": "accurate" in q or "高精度" in q,
        }
    )
    qc_tools = ["fastp", "filter_host"]
    if bio.get("enable_host_filter") is False:
        qc_tools = ["fastp"]

    tasks: list[TaskSpec] = [
        {"name": "quality_control", "agent": "QC Agent", "tools": qc_tools, "params": {}, "depends_on": []},
        {
            "name": "taxonomy_profile",
            "agent": "Taxonomy Agent",
            "tools": tax_tools,
            "params": {"confidence": 0.05},
            "depends_on": ["quality_control"],
        },
    ]
    if wants_assembly or pipe.get("enable_assembly", False):
        assembler = bio.get("assembler_preference") or pipe.get("default_assembler", "megahit")
        binners = list(
            bio.get("binners_preference")
            or pipe.get("binners")
            or (["metabat2", "maxbin2", "vamb"] if assembler == "flye" else ["metabat2", "maxbin2"])
        )
        asm_tools = ["megahit", "metaspades", "metabat2", "maxbin2", "checkm2", "gtdbtk"]
        if assembler == "flye":
            asm_tools = ["flye"] + [t for t in asm_tools if t != "megahit"]
        if "vamb" in [b.lower() for b in binners]:
            asm_tools.append("vamb")
        tasks.append(
            {
                "name": "assembly_binning",
                "agent": "Assembly Agent",
                "tools": asm_tools,
                "params": {
                    "assembler": assembler,
                    "binners": binners,
                    "complexity": "high" if bio.get("high_complexity") else "low",
                },
                "depends_on": ["quality_control"],
            }
        )
    if wants_function or pipe.get("enable_functional", True):
        tasks.append(
            {
                "name": "functional_annotation",
                "agent": "Function Agent",
                "tools": ["diamond", "eggnog", "humann"],
                "params": {"disease_context": bio.get("disease_context")},
                "depends_on": ["quality_control"],
            }
        )
    if wants_resistance or pipe.get("enable_arg", True):
        tasks.append(
            {
                "name": "resistance_virulence",
                "agent": "Resistance Agent",
                "tools": ["rgi", "deeparg", "resfinder", "amrfinderplus", "vfdb"],
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
                "params": {"expected_markers": bio.get("expected_markers") or []},
                "depends_on": ["taxonomy_profile"],
            }
        )
    tasks.extend(
        [
            {"name": "quality_critique", "agent": "Critic Agent", "tools": [], "params": {}, "depends_on": [t["name"] for t in tasks]},
            {"name": "literature_reasoning", "agent": "Literature Agent", "tools": ["pubmed", "rag"], "params": {}, "depends_on": ["quality_critique"]},
            {"name": "evidence_integration", "agent": "Evidence Agent", "tools": ["kg"], "params": {}, "depends_on": ["literature_reasoning"]},
            {"name": "scientific_review", "agent": "Reviewer Agent", "tools": [], "params": {}, "depends_on": ["evidence_integration"]},
            {"name": "report_generation", "agent": "Report Agent", "tools": [], "params": {}, "depends_on": ["scientific_review"]},
        ]
    )
    return tasks


def _tasks_to_dag(tasks: list[TaskSpec]) -> list[DagNode]:
    nodes: list[DagNode] = []
    # Graph-level agents (not swarm): critic/literature/evidence/reviewer/report
    skip_swarm = {
        "critic",
        "literature",
        "report",
        "evidence",
        "evidence_integration",
        "reviewer",
        "scientific_review",
        "reflection",
        "code",
    }
    for t in tasks:
        agent = _normalize_agent(t["agent"])
        if agent in skip_swarm or t["name"] in skip_swarm:
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
    config = dict(state["config"] or {})
    samples = state.get("samples", []) or []
    read_lengths = [float(s.get("read_length_est") or 150) for s in samples] or [150.0]
    config["_n_samples"] = len(samples)
    config["_read_length"] = max(read_lengths)

    env = probe_environment()
    memory = ContextMemory(Path(state["outdir"]) / "context")
    project = {
        "project": (config.get("project") or {}).get("name")
        or _infer_project_name(state.get("user_query") or ""),
        "host": (config.get("project") or {}).get("host", "human"),
        "platform": (config.get("project") or {}).get("platform", "illumina"),
        "read_length": f"PE{int(config['_read_length'])}"
        if config["_read_length"] < 1000
        else f"long:{int(config['_read_length'])}",
        "query": state.get("user_query"),
        "n_samples": len(samples),
    }
    memory.set_project_profile(project)
    memory.update(samples=samples, env=env)

    tasks = _llm_plan(state["user_query"], samples, config)
    source = "llm"
    bio = (state.get("artifacts") or {}).get("bio_reasoning") or {}
    if tasks is None:
        tasks = _default_plan(state["user_query"], config, bio=bio)
        source = "heuristic+bio_reasoning" if bio else "heuristic"
    elif bio:
        # Soft-apply assembler / host preferences onto LLM plan
        for t in tasks:
            if _normalize_agent(t["agent"]) == "assembly" and bio.get("assembler_preference"):
                t.setdefault("params", {})["assembler"] = bio["assembler_preference"]
        source = "llm+bio_reasoning"

    dag = _tasks_to_dag(tasks)
    memory.update(tasks=tasks, dag=dag, project=project, bio_reasoning=bio)
    memory.append_history(f"supervisor_plan:{source}:{len(tasks)}")

    hitl: list[str] = list(state.get("hitl_pending") or [])
    if any(n["agent"] == "assembly" for n in dag):
        hitl.append("Confirm assembly & binning strategy (MEGAHIT vs metaSPAdes; enable CheckM2/GTDB-Tk)?")
    if any(n["agent"] == "statistics" for n in dag) and not any(s.get("group") for s in state.get("samples", [])):
        hitl.append("Statistics planned but no sample groups in metadata — provide --metadata or confirm demo_mode?")

    task_json = {
        "tasks": [{"name": t["name"], "agent": t["agent"]} for t in tasks],
        "bio_reasoning_goal": bio.get("study_goal"),
        "bio_reasoning_assay": bio.get("recommended_assay"),
    }
    (Path(state["outdir"]) / "supervisor_plan.json").write_text(
        json.dumps(task_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    amsg = emit("supervisor", "executor", "plan", {"source": source, "n_tasks": len(tasks), "plan": task_json})
    return {
        "tasks": tasks,
        "dag": dag,
        "hitl_pending": hitl,
        "artifacts": {
            **state.get("artifacts", {}),
            "env": env,
            "plan_source": source,
            "supervisor_plan": task_json,
            "project_profile": project,
        },
        "messages": state.get("messages", []) + [f"Supervisor planned {len(tasks)} task(s) via {source}"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }


def _infer_project_name(query: str) -> str:
    q = query.lower()
    if "ibd" in q:
        return "IBD cohort"
    if "tumor" in q or "cancer" in q:
        return "tumor microbiome"
    return "metagenome project"


decompose = plan
