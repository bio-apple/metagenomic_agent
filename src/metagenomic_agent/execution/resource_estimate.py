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
    samples = state.get("samples") or []
    n = max(len(samples), 1)
    dag = state.get("dag") or []
    cfg = state.get("config") or {}
    linux = cfg.get("linux") or {}
    avail_mem = float(linux.get("memory_gb") or 32)
    threads = int(linux.get("threads") or 8)
    mode = state.get("mode") or "mock"

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
        warnings.append("Assembly/binning is long-running; enable execution.engine=nextflow|snakemake with -resume.")
    if mode in {"docker", "apptainer"} and n >= 10:
        warnings.append("Large cohort in containers: ensure disk for image layers + intermediate FASTQ/BAM.")

    engine = (cfg.get("execution") or {}).get("engine", "langgraph")
    resume = {
        "langgraph_step_cache": (cfg.get("cache") or {}).get("enabled", True),
        "nextflow_resume": engine == "nextflow",
        "snakemake_rerun_incomplete": engine == "snakemake",
        "hint": (
            "Set execution.engine to nextflow (uses -resume) or snakemake (--rerun-incomplete). "
            "LangGraph swarm uses cache/steps/ to skip completed nodes."
        ),
    }

    report = {
        "n_samples": n,
        "mode": mode,
        "available_memory_gb": avail_mem,
        "threads": threads,
        "stages": stages,
        "est_total_wall_hours": round(total_h, 3),
        "est_peak_memory_gb": peak_mem,
        "est_disk_gb": round(disk, 2),
        "warnings": warnings,
        "resume": resume,
        "user_message": (
            f"预估墙钟时间 ≈ {total_h:.2f} h（{n} 样本，mode={mode}）；"
            f"峰值内存 ≈ {peak_mem:.0f} GB；磁盘 ≈ {disk:.1f} GB。"
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
