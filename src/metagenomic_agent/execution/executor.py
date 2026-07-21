"""DAG executor with Monitor JSONL observability and optional external engine."""

from __future__ import annotations

import time
import uuid
import json
from pathlib import Path
from typing import Any

from metagenomic_agent.agents import AGENT_REGISTRY
from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.execution.engine import detect_engine, launch_external, write_nextflow_config
from metagenomic_agent.execution.monitor import Monitor
from metagenomic_agent.messaging import append_msg, emit
from metagenomic_agent.execution.step_cache import StepCache, merge_cached_into_artifacts
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
    agent_messages = list(state.get("agent_messages") or [])
    memory = ContextMemory(f"{state['outdir']}/context")
    stats_state = state.get("statistics")
    run_id = state.get("run_id") or str(uuid.uuid4())[:8]
    monitor = Monitor(Path(state["outdir"]) / "logs", run_id=run_id)

    try:
        nf_cfg = write_nextflow_config(Path(state["outdir"]) / "nextflow", state)
        artifacts["nextflow_config"] = str(nf_cfg)
        messages.append(f"Wrote Nextflow config: {nf_cfg}")
        monitor.log("engine", "nextflow_config_written", path=str(nf_cfg))
    except Exception as exc:  # noqa: BLE001
        messages.append(f"Nextflow config skipped: {exc}")

    engine = detect_engine(state.get("config", {}))
    artifacts["execution_engine"] = engine
    skip_swarm = False
    if engine in {"snakemake", "nextflow"}:
        ext = launch_external(engine, state, repo_root=Path(__file__).resolve().parents[3])
        artifacts["external_engine_result"] = ext
        monitor.log("engine", f"external_{engine}", status=ext.get("status"))
        messages.append(f"External engine {engine}: {ext.get('status')}")
        if ext.get("status") == "success":
            # Mutex: do not double-run heavy swarm when NF/SMK already completed compute
            skip_swarm = bool((state.get("config") or {}).get("execution", {}).get("skip_swarm_on_engine_ok", True))
            if skip_swarm:
                messages.append(f"Skipping LangGraph swarm (external {engine} succeeded)")
        elif ext.get("status") == "failed":
            artifacts.setdefault("errors", []).append(
                {"node": f"engine:{engine}", "error": ext.get("stderr") or "external failed", "classified": "logic"}
            )

    cache_cfg = (state.get("config") or {}).get("cache") or {}
    cache = StepCache(state["outdir"], enabled=bool(cache_cfg.get("enabled", True)))
    cache_hits = 0

    if skip_swarm:
        monitor.log("engine", "swarm_skipped", reason="external_ok")
        return {
            "dag": dag,
            "artifacts": artifacts,
            "messages": messages,
            "agent_messages": agent_messages,
            "statistics": stats_state,
            "run_id": run_id,
        }

    for node in _topo_sort(dag):
        if node.get("status") == "skipped":
            continue
        agent_name = node["agent"]
        fn = AGENT_REGISTRY.get(agent_name)
        if fn is None:
            messages.append(f"Unknown agent '{agent_name}', skipping")
            node["status"] = "skipped"
            continue

        hit = cache.lookup(node, state, artifacts)
        if hit and hit.get("artifacts_slice") and cache_cfg.get("enabled", True):
            artifacts = merge_cached_into_artifacts(artifacts, hit["artifacts_slice"])
            # Prefer full slice file if present
            key = hit.get("key")
            if key and key != "heuristic":
                entry = cache._index.get(key) or {}
                slice_file = entry.get("slice_file")
                if slice_file and Path(slice_file).exists():
                    try:
                        full = json.loads(Path(slice_file).read_text(encoding="utf-8"))
                        artifacts = merge_cached_into_artifacts(artifacts, full)
                    except (json.JSONDecodeError, OSError):
                        pass
            node["status"] = "cached"
            cache_hits += 1
            messages.append(f"CACHE HIT node={node['id']} source={hit.get('source')}")
            monitor.log("swarm", "cache_hit", node=node["id"], source=hit.get("source"))
            memory.append_history(f"cache:{node['id']}")
            continue

        # Mid-swarm critical HITL: confirm before Assembly / before statistics OTU filter
        hitl_cfg = (state.get("config") or {}).get("hitl") or {}
        auto_hitl = bool(state.get("hitl_auto_confirm") or hitl_cfg.get("auto_confirm", True))
        if agent_name == "assembly" and hitl_cfg.get("gate_before_assembly_run", True):
            if not artifacts.get("assembly_confirmed") and node.get("params", {}).get("hitl_skipped"):
                node["status"] = "skipped"
                messages.append(f"SKIP assembly node={node['id']} (HITL declined)")
                continue
            if not artifacts.get("assembly_confirmed") and not node.get("params", {}).get("hitl_confirmed"):
                from metagenomic_agent.agents.hitl_gates import build_assembly_gate, confirm_gate_inline

                gate = build_assembly_gate({**state, "artifacts": artifacts, "dag": dag, "config": state.get("config")})
                if gate:
                    action, patch = confirm_gate_inline(
                        {**state, "artifacts": artifacts, "dag": dag, "config": state.get("config")},
                        gate,
                        auto=auto_hitl,
                    )
                    if "config" in patch:
                        state = {**state, "config": patch["config"]}
                    if "dag" in patch:
                        dag = patch["dag"]
                        node = next((n for n in dag if n.get("id") == node.get("id")), node)
                    if patch.get("artifacts"):
                        artifacts = {**artifacts, **patch["artifacts"]}
                    messages.extend(patch.get("messages") or [])
                    monitor.log("swarm", "hitl_assembly", action=action)
                    if action == "skip_assembly" or node.get("status") == "skipped":
                        node["status"] = "skipped"
                        messages.append(f"SKIP assembly after HITL action={action}")
                        continue
        if agent_name in {"statistics", "stats"} and hitl_cfg.get("gate_before_otu_filter", True):
            if not artifacts.get("otu_filter_confirmed"):
                from metagenomic_agent.agents.hitl_gates import build_otu_filter_gate, confirm_gate_inline

                gate = build_otu_filter_gate({**state, "artifacts": artifacts, "dag": dag, "config": state.get("config")})
                if gate:
                    action, patch = confirm_gate_inline(
                        {**state, "artifacts": artifacts, "dag": dag, "config": state.get("config")},
                        gate,
                        auto=auto_hitl,
                    )
                    if "config" in patch:
                        state = {**state, "config": patch["config"]}
                    if patch.get("artifacts"):
                        artifacts = {**artifacts, **patch["artifacts"]}
                    messages.extend(patch.get("messages") or [])
                    monitor.log("swarm", "hitl_otu_filter", action=action)

        t0 = time.time()
        messages.append(f"Running agent={agent_name} node={node['id']}")
        monitor.log("swarm", "start", node=node["id"], agent=agent_name)
        memory.append_history(f"start:{node['id']}")
        try:
            produced = fn(state={**state, "artifacts": artifacts}, node=node)
            if "_statistics_state" in produced:
                stats_state = produced.pop("_statistics_state")
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
            monitor.log("swarm", "done", node=node["id"], latency_s=round(elapsed, 3))
            agent_messages = append_msg(
                agent_messages,
                emit(agent_name, "coordinator", "result", {"node": node["id"], "latency_s": elapsed}),
            )
            memory.append_history(f"done:{node['id']}:{elapsed:.2f}s")
            try:
                cache.store(node, state, produced, Path(state["outdir"]))
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            node["status"] = "failed"
            messages.append(f"FAILED {node['id']}: {exc}")
            monitor.log("swarm", "fail", level="error", node=node["id"], error=str(exc))
            memory.append_history(f"fail:{node['id']}:{exc}")
            artifacts.setdefault("errors", []).append(
                {"node": node["id"], "error": str(exc), "classified": classify_error(None, str(exc))}
            )

    artifacts["monitor"] = monitor.snapshot()
    artifacts["step_cache"] = {"hits": cache_hits, "index": str(cache.index_path)}

    # Summary-driven context: statistical metadata only (never raw sequences)
    from metagenomic_agent.coordinator.summary import write_pipeline_summary
    from metagenomic_agent.report.workflow_export import resolve_run_seed

    run_seed = resolve_run_seed({**state, "artifacts": artifacts, "run_id": run_id})
    artifacts["run_seed"] = run_seed
    summary_full = write_pipeline_summary({**state, "artifacts": artifacts, "dag": dag, "run_id": run_id})
    llm_ctx = summary_full.pop("_llm_context", "")
    artifacts["pipeline_summary"] = {k: v for k, v in summary_full.items() if not k.startswith("_")}
    artifacts["llm_context"] = llm_ctx

    memory.update(artifacts=artifacts, dag=dag, pipeline_summary=artifacts["pipeline_summary"], run_seed=run_seed)
    result: dict[str, Any] = {
        "artifacts": artifacts,
        "dag": dag,
        "messages": messages
        + [
            f"Pipeline summary written (metadata-only context); seed={run_seed}",
            f"Step cache hits={cache_hits}",
        ],
        "agent_messages": agent_messages,
        "run_id": run_id,
    }
    if stats_state is not None:
        result["statistics"] = stats_state
    return result
