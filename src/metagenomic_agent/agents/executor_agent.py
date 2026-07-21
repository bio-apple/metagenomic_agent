"""Executor / Bioinfo Agent — container-aware HPC submit + capped resources + swarm.

SLURM / PBS / SGE scripts use cluster load sensing so requests stay under kill thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.deployment.slurm import write_scheduler_scripts
from metagenomic_agent.execution.cluster import cap_resources, sense_cluster
from metagenomic_agent.execution.self_heal import deep_merge_config
from metagenomic_agent.execution.workflow_params import write_workflow_params
from metagenomic_agent.messaging import append_msg, emit


def _k8s_job(state: dict[str, Any], params: dict[str, str], allocation: dict[str, Any]) -> dict[str, Any]:
    cfg = state.get("config") or {}
    threads = int(allocation.get("threads") or 8)
    mem = int(allocation.get("memory_gb") or 32)
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": f"meta-agent-{state.get('run_id') or 'run'}"},
        "spec": {
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "meta-agent",
                            "image": (cfg.get("docker") or {}).get("agent_image")
                            or "ghcr.io/bio-apple/metagenomic_agent:latest",
                            "resources": {
                                "requests": {"cpu": str(threads), "memory": f"{mem}Gi"},
                                "limits": {"cpu": str(threads), "memory": f"{mem}Gi"},
                            },
                            "args": [
                                "run",
                                "--input",
                                str(state.get("input_path")),
                                "--outdir",
                                "/out",
                                "--mode",
                                str(state.get("mode") or "docker"),
                                "--yes",
                            ],
                            "env": [
                                {"name": "AGENT_PARAMS", "value": params.get("params_yaml", "")},
                                {
                                    "name": "APPTAINER_CACHEDIR",
                                    "value": str((cfg.get("apptainer") or {}).get("sif_dir") or "/scratch/containers"),
                                },
                            ],
                        }
                    ],
                }
            }
        },
        "notes": "Mount input/out volumes; resources pre-capped by cluster sense.",
    }


def prepare_submit_specs(state: dict[str, Any]) -> dict[str, Any]:
    """Sense cluster → cap CPU/mem/GPU → write SLURM/PBS/SGE/K8s + params."""
    cfg = dict(state.get("config") or {})
    sense = sense_cluster(cfg)
    capped = cap_resources(cfg, sense)
    alloc = {
        "threads": capped["linux"]["threads"],
        "memory_gb": capped["linux"]["memory_gb"],
        "gpus": capped["linux"].get("gpus") or 0,
    }
    # Persist capped resources into config for swarm / engine
    new_cfg = deep_merge_config(cfg, {"linux": capped["linux"], "docker": capped["docker"]})
    state = {**state, "config": new_cfg}

    params = write_workflow_params(state)
    out = Path(state["outdir"]) / "executor"
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(parents=True, exist_ok=True)

    sched_paths = write_scheduler_scripts(out, state, allocation=alloc)
    k8s = _k8s_job(state, params, alloc)
    (out / "job.k8s.yaml").write_text(json.dumps(k8s, indent=2), encoding="utf-8")
    (out / "cluster_sense.json").write_text(json.dumps(sense, indent=2), encoding="utf-8")
    (out / "resource_allocation.json").write_text(
        json.dumps({"allocation": alloc, "cap": capped, "sense": sense}, indent=2), encoding="utf-8"
    )

    scheduler = sense.get("scheduler") or "local"
    submit_hint = {
        "slurm": f"sbatch {sched_paths['slurm']}",
        "pbs": f"qsub {sched_paths['pbs']}",
        "sge": f"qsub {sched_paths['sge']}",
        "local": "meta-agent run … (inline swarm)",
    }.get(scheduler, f"sbatch {sched_paths['slurm']}")

    (out / "SUBMIT.md").write_text(
        "# Executor — HPC / cloud-native submit\n\n"
        f"- Detected scheduler: `{scheduler}` (pressure={sense.get('pressure')})\n"
        f"- Capped allocation: {alloc['threads']} CPUs, {alloc['memory_gb']} GB, "
        f"{alloc['gpus']} GPU(s) — reason: {capped.get('reason')}\n"
        f"- Preferred submit: `{submit_hint}`\n"
        f"- SLURM: `{sched_paths['slurm']}`\n"
        f"- PBS: `{sched_paths['pbs']}`\n"
        f"- SGE: `{sched_paths['sge']}`\n"
        f"- K8s: `{out / 'job.k8s.yaml'}`\n"
        f"- Params: `{params.get('params_yaml')}`\n"
        f"- Containers: mode=`{state.get('mode')}`; BioContainers via Docker/Apptainer; "
        "set `apptainer.sif_dir` for SIF cache on HPC.\n"
        "- Assembly checkpoints: `outdir/<sample>/assembly/` reused when present.\n",
        encoding="utf-8",
    )
    return {
        "slurm": sched_paths["slurm"],
        "pbs": sched_paths["pbs"],
        "sge": sched_paths["sge"],
        "k8s": str(out / "job.k8s.yaml"),
        "readme": str(out / "SUBMIT.md"),
        "params": params,
        "sense": sense,
        "allocation": alloc,
        "config": new_cfg,
        "submit_hint": submit_hint,
    }


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    from metagenomic_agent.execution.executor import execute_swarm

    arts = dict(state.get("artifacts") or {})
    specs = prepare_submit_specs(state)
    arts["executor"] = {
        "role": "executor_bioinfo",
        "slurm": specs["slurm"],
        "pbs": specs["pbs"],
        "sge": specs["sge"],
        "k8s": specs["k8s"],
        "params": specs["params"],
        "cluster_sense": specs["sense"],
        "allocation": specs["allocation"],
        "submit_hint": specs["submit_hint"],
        "policy": "sense_cap_then_containerized_swarm_or_scheduler",
    }
    amsg = emit(
        "executor",
        "qc_critic",
        "status",
        {"scheduler": specs["sense"].get("scheduler"), "allocation": specs["allocation"]},
    )
    pre = {
        **state,
        "config": specs["config"],
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [
            f"Executor sense={specs['sense'].get('scheduler')}/"
            f"{specs['sense'].get('pressure')} → "
            f"{specs['allocation']['threads']}c/{specs['allocation']['memory_gb']}G"
        ],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }
    result = execute_swarm(pre)
    result_arts = dict(result.get("artifacts") or {})
    result_arts["executor"] = arts["executor"]
    result["artifacts"] = result_arts
    result["config"] = specs["config"]
    result["messages"] = list(result.get("messages") or []) + ["Executor finished swarm/engine handoff"]
    return result
