"""Cluster load sensing + resource capping for SLURM / PBS / SGE.

Avoids over-subscription that leads to OOM kills (exit 137) on shared HPC.
When schedulers are unavailable (laptop/CI), returns a safe local probe.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any, Literal

SchedulerName = Literal["slurm", "pbs", "sge", "local", "auto"]


def detect_scheduler(config: dict[str, Any] | None = None) -> SchedulerName:
    cfg = (config or {}).get("linux") or {}
    preferred = str(cfg.get("scheduler") or "auto").lower()
    if preferred in {"slurm", "pbs", "sge", "local"}:
        if preferred == "slurm" and not shutil.which("squeue") and not shutil.which("sinfo"):
            return "local"
        if preferred == "pbs" and not shutil.which("qstat"):
            return "local"
        if preferred == "sge" and not (shutil.which("qstat") or shutil.which("qhost")):
            return "local"
        return preferred  # type: ignore[return-value]
    if shutil.which("squeue") or shutil.which("sinfo"):
        return "slurm"
    if shutil.which("qstat") and (cfg.get("pbs") or os.environ.get("PBS_HOME")):
        return "pbs"
    if shutil.which("qstat") or shutil.which("qhost"):
        # Ambiguous PBS vs SGE — prefer sge if SGE_ROOT set
        if os.environ.get("SGE_ROOT"):
            return "sge"
        if os.environ.get("PBS_HOME") or os.environ.get("PBS_JOBID"):
            return "pbs"
        return "sge"
    return "local"


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def sense_cluster(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Probe queue depth / free resources; never raises."""
    scheduler = detect_scheduler(config)
    linux = (config or {}).get("linux") or {}
    report: dict[str, Any] = {
        "scheduler": scheduler,
        "available": False,
        "queue_depth": None,
        "nodes_idle": None,
        "cpus_free_hint": None,
        "mem_free_gb_hint": None,
        "gpus_free_hint": None,
        "raw_excerpt": "",
        "pressure": "unknown",  # low | medium | high
    }

    if scheduler == "slurm":
        q = _run(["squeue", "-h", "-o", "%i"])
        jobs = [ln for ln in q.splitlines() if ln.strip()]
        report["queue_depth"] = len(jobs)
        report["available"] = True
        info = _run(["sinfo", "-h", "-o", "%a %D %C %m"])
        report["raw_excerpt"] = (info or q)[:500]
        # Parse first partition free CPUs if present (format varies)
        idle = _run(["sinfo", "-h", "-t", "idle", "-o", "%D"])
        try:
            report["nodes_idle"] = sum(int(x) for x in re.findall(r"\d+", idle)[:5]) or None
        except ValueError:
            report["nodes_idle"] = None
        if report["queue_depth"] is not None:
            if report["queue_depth"] > 80 or (report["nodes_idle"] == 0):
                report["pressure"] = "high"
            elif report["queue_depth"] > 20:
                report["pressure"] = "medium"
            else:
                report["pressure"] = "low"

    elif scheduler == "pbs":
        q = _run(["qstat", "-Q"])
        report["available"] = bool(q.strip())
        report["raw_excerpt"] = q[:500]
        # Count running/queued lines from qstat
        allj = _run(["qstat"])
        lines = [ln for ln in allj.splitlines() if ln.strip() and not ln.startswith("Job")]
        report["queue_depth"] = max(0, len(lines) - 1) if lines else 0
        report["pressure"] = "high" if (report["queue_depth"] or 0) > 50 else (
            "medium" if (report["queue_depth"] or 0) > 15 else "low"
        )

    elif scheduler == "sge":
        q = _run(["qstat", "-g", "c"])
        report["available"] = True
        report["raw_excerpt"] = q[:500]
        allj = _run(["qstat"])
        lines = [ln for ln in allj.splitlines() if re.match(r"^\s*\d+", ln)]
        report["queue_depth"] = len(lines)
        report["pressure"] = "high" if len(lines) > 50 else ("medium" if len(lines) > 15 else "low")

    else:
        # Local machine: use os.cpu_count + optional /proc/meminfo
        cpus = os.cpu_count() or 4
        report["available"] = True
        report["cpus_free_hint"] = cpus
        report["pressure"] = "low"
        meminfo = mem_free_gb()
        if meminfo is not None:
            report["mem_free_gb_hint"] = meminfo
            if meminfo < 8:
                report["pressure"] = "high"
            elif meminfo < 24:
                report["pressure"] = "medium"

    # Configured GPU request
    report["gpus_requested"] = int(linux.get("gpus") or 0)
    return report


def mem_free_gb() -> float | None:
    try:
        text = open("/proc/meminfo", encoding="utf-8").read()
    except OSError:
        # macOS fallback via sysctl
        out = _run(["sysctl", "-n", "hw.memsize"])
        try:
            total = int(out.strip()) / (1024**3)
            # Without free stats, assume ~50% available
            return round(total * 0.5, 1)
        except ValueError:
            return None
    m = re.search(r"MemAvailable:\s+(\d+)", text)
    if not m:
        m = re.search(r"MemFree:\s+(\d+)", text)
    if not m:
        return None
    return round(int(m.group(1)) / (1024**2), 1)


def cap_resources(
    config: dict[str, Any],
    sense: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a linux/docker patch that caps threads/memory under cluster pressure.

    Policy: never request more than available hints; under high pressure shrink
    requests so the scheduler is less likely to kill the job.
    """
    linux = dict((config or {}).get("linux") or {})
    docker = dict((config or {}).get("docker") or {})
    sense = sense or sense_cluster(config)
    threads = int(docker.get("threads") or linux.get("threads") or 8)
    mem = int(linux.get("memory_gb") or 32)
    gpus = int(linux.get("gpus") or 0)
    patch: dict[str, Any] = {"linux": {}, "docker": {}, "sense": sense}

    # Cap by free hints when present
    if sense.get("cpus_free_hint"):
        threads = min(threads, max(2, int(sense["cpus_free_hint"]) - 1))
    if sense.get("mem_free_gb_hint"):
        mem = min(mem, max(4, int(float(sense["mem_free_gb_hint"]) * 0.8)))

    pressure = sense.get("pressure") or "unknown"
    if pressure == "high":
        threads = max(2, threads // 2)
        mem = max(8, mem // 2)
        if gpus > 1:
            gpus = 1
        patch["reason"] = "high_cluster_pressure_reduce_request"
    elif pressure == "medium":
        threads = max(2, int(threads * 0.75))
        mem = max(8, int(mem * 0.85))
        patch["reason"] = "medium_cluster_pressure_soft_cap"
    else:
        patch["reason"] = "no_cap_or_local_ok"

    # Hard ceilings from config
    max_t = int(linux.get("max_threads") or 64)
    max_m = int(linux.get("max_memory_gb") or 256)
    threads = min(threads, max_t)
    mem = min(mem, max_m)

    patch["linux"]["threads"] = threads
    patch["linux"]["memory_gb"] = mem
    patch["linux"]["gpus"] = gpus
    patch["docker"]["threads"] = threads
    return patch
