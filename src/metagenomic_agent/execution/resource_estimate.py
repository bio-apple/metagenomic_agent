"""Pre-run resource estimation and production readiness hints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Rough wall-time / memory heuristics (hours, GB) per sample for common stages
_STAGE_COST = {
    "qc": {"hours": 0.15, "mem_gb": 4, "disk_gb": 2},
    "qc_host": {"hours": 0.25, "mem_gb": 8, "disk_gb": 3},
    "taxonomy": {"hours": 0.5, "mem_gb": 32, "disk_gb": 5},
    "functional": {"hours": 1.0, "mem_gb": 16, "disk_gb": 8},
    "function": {"hours": 1.0, "mem_gb": 16, "disk_gb": 8},
    "assembly": {"hours": 4.0, "mem_gb": 64, "disk_gb": 40},
    "statistics": {"hours": 0.1, "mem_gb": 4, "disk_gb": 1},
    "visualization": {"hours": 0.05, "mem_gb": 2, "disk_gb": 0.5},
}


def estimate_resources(state: dict[str, Any]) -> dict[str, Any]:
    from metagenomic_agent.execution.cluster import cap_resources, sense_cluster

    samples = state.get("samples") or []
    n = max(len(samples), 1)
    dag = state.get("dag") or []
    cfg = state.get("config") or {}
    linux = cfg.get("linux") or {}
    avail_mem = float(linux.get("memory_gb") or 32)
    threads = int(linux.get("threads") or 8)
    mode = state.get("mode") or "mock"
    sense = sense_cluster(cfg)
    capped = cap_resources(cfg, sense)
    threads = int(capped["linux"]["threads"])
    avail_mem = float(capped["linux"]["memory_gb"])

    stages: list[dict[str, Any]] = []
    total_h = 0.0
    peak_mem = 0.0
    disk = 0.0
    agents = {n.get("agent") for n in dag if n.get("status") != "skipped"}
    if not agents:
        agents = {"qc", "taxonomy", "functional", "statistics"}

    for agent in agents:
        cost = _STAGE_COST.get(agent) or {"hours": 0.2, "mem_gb": 8, "disk_gb": 2}
        # Parallelism across samples limited by threads (assume 1 sample / 4 threads for heavy tools)
        parallel = max(1, threads // 4) if agent in {"taxonomy", "assembly", "functional"} else max(1, min(n, threads))
        wall = cost["hours"] * n / parallel
        if mode == "mock":
            wall *= 0.01
        stages.append(
            {
                "agent": agent,
                "est_wall_hours": round(wall, 3),
                "est_mem_gb": cost["mem_gb"],
                "est_disk_gb": round(cost["disk_gb"] * n, 2),
            }
        )
        total_h += wall
        peak_mem = max(peak_mem, float(cost["mem_gb"]))
        disk += cost["disk_gb"] * n

    warnings: list[str] = []
    if peak_mem > avail_mem and mode not in {"mock"}:
        warnings.append(
            f"Peak estimated memory {peak_mem:.0f} GB exceeds config linux.memory_gb={avail_mem:.0f}. "
            "Prefer MEGAHIT over metaSPAdes or raise memory / use HPC."
        )
    if "assembly" in agents and mode not in {"mock"}:
        warnings.append(
            "Assembly/binning is long-running; enable cache.per_sample_assembly + "
            "execution.engine=nextflow|snakemake (-resume / --rerun-incomplete)."
        )
    if mode in {"docker", "apptainer"} and n >= 10:
        warnings.append("Large cohort in containers: ensure disk for BioContainers layers + intermediates.")
    if sense.get("pressure") == "high":
        warnings.append(
            f"Cluster pressure high (scheduler={sense.get('scheduler')}, queue={sense.get('queue_depth')}); "
            f"capped request to {threads} CPUs / {avail_mem:.0f} GB to avoid kills."
        )

    engine = (cfg.get("execution") or {}).get("engine", "langgraph")
    resume = {
        "langgraph_step_cache": (cfg.get("cache") or {}).get("enabled", True),
        "per_sample_assembly_checkpoint": (cfg.get("cache") or {}).get("per_sample_assembly", True),
        "nextflow_resume": engine == "nextflow",
        "snakemake_rerun_incomplete": engine == "snakemake",
        "hint": (
            "Assembly checkpoints live under outdir/<sample>/assembly/; "
            "swarm cache/steps/ skips completed nodes; NF -resume / SMK --rerun-incomplete."
        ),
    }

    report = {
        "n_samples": n,
        "mode": mode,
        "available_memory_gb": avail_mem,
        "threads": threads,
        "gpus": int(capped["linux"].get("gpus") or 0),
        "stages": stages,
        "est_total_wall_hours": round(total_h, 3),
        "est_peak_memory_gb": peak_mem,
        "est_disk_gb": round(disk, 2),
        "warnings": warnings,
        "resume": resume,
        "cluster_sense": sense,
        "allocation_cap": {
            "threads": threads,
            "memory_gb": avail_mem,
            "gpus": capped["linux"].get("gpus"),
            "reason": capped.get("reason"),
        },
        "containers": {
            "backend": mode if mode in {"docker", "apptainer"} else (cfg.get("sandbox") or {}).get("backend"),
            "biocontainers": True,
            "apptainer_sif_dir": (cfg.get("apptainer") or {}).get("sif_dir"),
        },
        "user_message": (
            f"预估墙钟时间 ≈ {total_h:.2f} h（{n} 样本，mode={mode}）；"
            f"申请资源 ≈ {threads} CPU / {avail_mem:.0f} GB"
            f"（集群={sense.get('scheduler')}, pressure={sense.get('pressure')}）；"
            f"峰值估算 ≈ {peak_mem:.0f} GB；磁盘 ≈ {disk:.1f} GB。"
            + ((" 警告: " + "; ".join(warnings)) if warnings else "")
        ),
    }
    return report


def write_resource_estimate(state: dict[str, Any]) -> dict[str, Any]:
    report = estimate_resources(state)
    out = Path(state["outdir"]) / "resource_estimate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (Path(state["outdir"]) / "resource_estimate.md").write_text(
        "# Resource estimate\n\n"
        + report["user_message"]
        + "\n\n## Resume\n\n"
        + f"- {report['resume']['hint']}\n",
        encoding="utf-8",
    )
    report["path"] = str(out)
    return report
