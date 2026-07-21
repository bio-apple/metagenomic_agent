"""DAG executor and lightweight progress monitor."""

from __future__ import annotations

import time
from typing import Any

from metagenomic_agent.agents import AGENT_REGISTRY
from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.state import AgentState


def _topo_sort(dag: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {n["id"]: n for n in dag}
    seen: set[str] = set()
    order: list[dict[str, Any]] = []

    def visit(nid: str) -> None:
        if nid in seen:
            return
        node = by_id[nid]
        for dep in node.get("depends_on", []):
            if dep in by_id:
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
    order = _topo_sort(dag)

    for node in order:
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
            for k, v in produced.items():
                if isinstance(v, dict) and isinstance(artifacts.get(k), dict):
                    artifacts[k].update(v)
                else:
                    artifacts[k] = v
            node["status"] = "done"
            elapsed = time.time() - t0
            messages.append(f"Finished {node['id']} in {elapsed:.2f}s")
            memory.append_history(f"done:{node['id']}:{elapsed:.2f}s")
        except Exception as exc:  # noqa: BLE001 — surface to validator/recovery
            node["status"] = "failed"
            messages.append(f"FAILED {node['id']}: {exc}")
            memory.append_history(f"fail:{node['id']}:{exc}")
            artifacts.setdefault("errors", []).append({"node": node["id"], "error": str(exc)})

    memory.update(artifacts=artifacts, dag=dag)
    return {"artifacts": artifacts, "dag": dag, "messages": messages}
