"""Docker / Apptainer / shell command helpers with resource & platform controls."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass
class RunResult:
    ok: bool
    command: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


def run_command(cmd: str | Sequence[str], check: bool = True) -> RunResult:
    if isinstance(cmd, (list, tuple)):
        command = " ".join(str(c) for c in cmd)
        proc = subprocess.run(list(cmd), capture_output=True, text=True)
    else:
        command = cmd
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    result = RunResult(
        ok=proc.returncode == 0,
        command=command,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )
    if check and not result.ok:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}\n{result.stderr}")
    return result


def docker_run(
    image: str,
    inner_cmd: str,
    volumes: dict[str, str],
    check: bool = True,
    platform: str | None = None,
    memory_gb: int | None = None,
    cpus: int | None = None,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
) -> RunResult:
    """Run command inside Docker with optional platform (amd64 on Apple Silicon) and limits."""
    parts = ["docker", "run", "--rm"]
    if platform:
        parts.extend(["--platform", platform])
    if memory_gb:
        parts.extend(["--memory", f"{int(memory_gb)}g"])
    if cpus:
        parts.extend(["--cpus", str(cpus)])
    if workdir:
        parts.extend(["-w", workdir])
    for k, v in (env or {}).items():
        parts.extend(["-e", f"{k}={v}"])
    for host, container in volumes.items():
        parts.extend(["-v", f"{host}:{container}"])
    parts.extend([image, "sh", "-c", inner_cmd])
    return run_command(parts, check=check)


def apptainer_run(
    image_or_sif: str,
    inner_cmd: str,
    volumes: dict[str, str],
    check: bool = True,
    env: dict[str, str] | None = None,
) -> RunResult:
    """Run via Apptainer or Singularity (HPC-friendly)."""
    binary = shutil.which("apptainer") or shutil.which("singularity")
    if not binary:
        return RunResult(
            ok=False,
            command=f"apptainer exec {image_or_sif} {inner_cmd}",
            stderr="apptainer/singularity not found on PATH",
            returncode=127,
        )
    parts = [binary, "exec", "--cleanenv"]
    for host, container in volumes.items():
        parts.extend(["--bind", f"{host}:{container}"])
    for k, v in (env or {}).items():
        parts.extend(["--env", f"{k}={v}"])
    parts.extend([image_or_sif, "sh", "-c", inner_cmd])
    return run_command(parts, check=check)
