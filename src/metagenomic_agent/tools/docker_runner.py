"""Docker / shell command helpers."""

from __future__ import annotations

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


def docker_run(image: str, inner_cmd: str, volumes: dict[str, str], check: bool = True) -> RunResult:
    parts = ["docker", "run", "--rm"]
    for host, container in volumes.items():
        parts.extend(["-v", f"{host}:{container}"])
    parts.extend([image, "sh", "-c", inner_cmd])
    return run_command(parts, check=check)
