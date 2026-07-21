"""DAG executor with structured error capture for self-healing."""

from __future__ import annotations

import time
from typing import Any

from metagenomic_agent.agents import AGENT_REGISTRY
from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.execution.engine import detect_engine, write_nextflow_config
from metagenomic_agent.tools.linux_runner import classify_error
from metagenomic_agent.state import AgentState


def _topo_sort(dag: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {n["id"]: n for n in dag}
    seen: set[str] = set()
    order: list[dict[str, Any]] = []

    def visit(nid: str) -> None:
        if nid in seen or nid not in by_id:
            return
        node = by_id[nid]
        for dep in node.get("depends_on", []):
            visit(dep)
        seen.add(nid)
        order.append(node)

    for n in dag:
        visit(n["id"])
    return order


def execute_swarm(state: AgentState) -> dict:
    dag = list(state.get("dag", []))
    artifacts = dict(state.get("artifacts", {}))
    messages = list(state.get("messages", []))
    memory = ContextMemory(f"{state['outdir']}/context")
    stats_state = state.get("statistics")

    # Planner/executor decoupling: always emit Nextflow config for Linux handoff
    try:
        nf_cfg = write_nextflow_config(__import__("pathlib").Path(state["outdir"]) / "nextflow", state)
        artifacts["nextflow_config"] = str(nf_cfg)
        messages.append(f"Wrote Nextflow config: {nf_cfg}")
    except Exception as exc:  # noqa: BLE001
        messages.append(f"Nextflow config skipped: {exc}")

    engine = detect_engine(state.get("config", {}))
    artifacts["execution_engine"] = engine

    for node in _topo_sort(dag):
        if node.get("status") == "skipped":
            continue
        agent_name = node["agent"]
        fn = AGENT_REGISTRY.get(agent_name)
        if fn is None:
            messages.append(f"Unknown agent '{agent_name}', skipping")
            node["status"] = "skipped"
            continue
        t0 = time.time()
        messages.append(f"Running agent={agent_name} node={node['id']}")
        memory.append_history(f"start:{node['id']}")
        try:
            produced = fn(state={**state, "artifacts": artifacts}, node=node)
            if "_statistics_state" in produced:
                stats_state = produced.pop("_statistics_state")
            # Merge structured tool errors from agents (e.g. assembly OOM)
            if "errors" in produced and isinstance(produced["errors"], list):
                artifacts.setdefault("errors", []).extend(produced.pop("errors"))
            for k, v in produced.items():
                if k == "artifacts" and isinstance(v, dict):
                    artifacts.update(v)
                elif isinstance(v, dict) and isinstance(artifacts.get(k), dict) and k not in {"statistics"}:
                    artifacts[k].update(v)
                else:
                    artifacts[k] = v
            if "statistics" in produced and isinstance(produced["statistics"], dict):
                stats_state = produced["statistics"]
            node["status"] = "done"
            elapsed = time.time() - t0
            messages.append(f"Finished {node['id']} in {elapsed:.2f}s")
            memory.append_history(f"done:{node['id']}:{elapsed:.2f}s")
        except Exception as exc:  # noqa: BLE001
            node["status"] = "failed"
            messages.append(f"FAILED {node['id']}: {exc}")
            memory.append_history(f"fail:{node['id']}:{exc}")
            artifacts.setdefault("errors", []).append(
                {
                    "node": node["id"],
                    "error": str(exc),
                    "classified": classify_error(None, str(exc)),
                }
            )

    memory.update(artifacts=artifacts, dag=dag)
    result = {"artifacts": artifacts, "dag": dag, "messages": messages}
    if stats_state is not None:
        result["statistics"] = stats_state
    return result
