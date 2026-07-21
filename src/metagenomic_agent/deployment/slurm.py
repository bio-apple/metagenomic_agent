"""Slurm / PBS batch script generation for HPC handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def render_sbatch(
    job_name: str,
    command: str,
    *,
    partition: str = "normal",
    cpus: int = 16,
    mem: str = "64G",
    time: str = "24:00:00",
    account: str | None = None,
    gpus: int = 0,
) -> str:
    lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --partition={partition}",
        f"#SBATCH --cpus-per-task={cpus}",
        f"#SBATCH --mem={mem}",
        f"#SBATCH --time={time}",
        f"#SBATCH --output={job_name}-%j.out",
        f"#SBATCH --error={job_name}-%j.err",
    ]
    if account:
        lines.append(f"#SBATCH --account={account}")
    if gpus:
        lines.append(f"#SBATCH --gres=gpu:{gpus}")
    lines.extend(["", "set -euo pipefail", command, ""])
    return "\n".join(lines)


def write_analysis_sbatch(outdir: str | Path, state: dict[str, Any]) -> Path:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    linux = state.get("config", {}).get("linux", {})
    cmd = (
        f"meta-agent run --input {state.get('input_path')} --outdir {state.get('outdir')} "
        f"--mode {state.get('mode')} --yes "
        f"--query {repr(state.get('user_query', ''))}"
    )
    script = render_sbatch(
        "meta-agent",
        cmd,
        partition=linux.get("slurm_queue", "normal"),
        cpus=int(linux.get("threads", 16)),
        mem=f"{int(linux.get('memory_gb', 64))}G",
    )
    path = out / "submit_meta_agent.sbatch"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
    return path
