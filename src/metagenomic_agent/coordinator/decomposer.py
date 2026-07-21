"""Dynamic task decomposer: LLM or default gut-metagenome DAG."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from metagenomic_agent.coordinator.env_manager import probe_environment
from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.state import AgentState, DagNode

KB_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "best_practices.md"


def _default_dag(config: dict[str, Any]) -> list[DagNode]:
    pipe = config.get("pipeline", {})
    taxonomy_tools = list(pipe.get("taxonomy_tools", ["kraken2", "metaphlan"]))
    nodes: list[DagNode] = [
        {
            "id": "qc",
            "agent": "qc_host",
            "tools": ["fastp"] + (["filter_host"] if pipe.get("enable_host_filter", True) else []),
            "params": {"enable_host_filter": bool(pipe.get("enable_host_filter", True))},
            "depends_on": [],
            "status": "pending",
        },
        {
            "id": "taxonomy",
            "agent": "taxonomy",
            "tools": taxonomy_tools,
            "params": {"tools": taxonomy_tools, "confidence": 0.05},
            "depends_on": ["qc"],
            "status": "pending",
        },
    ]
    if pipe.get("enable_functional", True):
        nodes.append(
            {
                "id": "functional",
                "agent": "functional",
                "tools": ["diamond"] if not pipe.get("enable_humann") else ["humann4"],
                "params": {},
                "depends_on": ["qc"],
                "status": "pending",
            }
        )
    if pipe.get("enable_assembly", False):
        nodes.append(
            {
                "id": "assembly",
                "agent": "assembly",
                "tools": ["megahit"],
                "params": {},
                "depends_on": ["qc"],
                "status": "pending",
            }
        )
    return nodes


def _kb_snippet(limit: int = 2500) -> str:
    if KB_PATH.exists():
        return KB_PATH.read_text(encoding="utf-8")[:limit]
    return ""


def _llm_decompose(query: str, samples: list[dict], config: dict[str, Any]) -> list[DagNode] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
    except ImportError:
        return None

    llm_cfg = config.get("llm", {})
    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", llm_cfg.get("model", "deepseek-chat")),
        temperature=llm_cfg.get("temperature", 0.2),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    schema_hint = {
        "nodes": [
            {
                "id": "qc",
                "agent": "qc_host|taxonomy|functional|assembly|stats|genomic_lm",
                "tools": ["fastp", "filter_host", "kraken2", "metaphlan", "diamond"],
                "params": {},
                "depends_on": [],
            }
        ]
    }
    prompt = (
        f"User query: {query}\n"
        f"Samples: {json.dumps(samples, ensure_ascii=False)}\n"
        f"Knowledge:\n{_kb_snippet()}\n"
        f"Return ONLY JSON matching: {json.dumps(schema_hint)}"
    )
    resp = model.invoke(
        [
            SystemMessage(content="You are a metagenomics workflow planner. Output JSON only."),
            HumanMessage(content=prompt),
        ]
    )
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    data = json.loads(match.group(0))
    nodes: list[DagNode] = []
    for n in data.get("nodes", []):
        nodes.append(
            DagNode(
                id=n["id"],
                agent=n["agent"],
                tools=list(n.get("tools", [])),
                params=dict(n.get("params", {})),
                depends_on=list(n.get("depends_on", [])),
                status="pending",
            )
        )
    return nodes or None


def decompose(state: AgentState) -> dict:
    config = state["config"]
    env = probe_environment(config.get("docker", {}).get("image", "meta:latest"))
    memory = ContextMemory(Path(state["outdir"]) / "context")
    memory.update(samples=state.get("samples", []), env=env)
    memory.append_history("decompose_start")

    nodes = _llm_decompose(state["user_query"], state.get("samples", []), config)
    source = "llm"
    if nodes is None:
        nodes = _default_dag(config)
        source = "default_template"

    hitl: list[str] = []
    if any(n["agent"] == "assembly" for n in nodes):
        hitl.append("Confirm assembly & binning strategy (MEGAHIT vs metaSPAdes)?")

    auto = state.get("hitl_auto_confirm", True) or config.get("hitl", {}).get("auto_confirm", True)
    if hitl and auto:
        memory.append_history("hitl_auto_confirmed: " + "; ".join(hitl))
        hitl = []

    memory.update(dag=nodes)
    memory.append_history(f"decompose_done:{source}")

    msg = f"Generated DAG with {len(nodes)} node(s) via {source}"
    return {
        "dag": nodes,
        "hitl_pending": hitl,
        "messages": state.get("messages", []) + [msg, f"Environment: {env}"],
        "artifacts": {**state.get("artifacts", {}), "env": env, "dag_source": source},
    }
