"""Linux production bioinformatics tool runner (Bioconda-isolated).

Implements the architecture doc's LinuxBioToolRunner pattern with structured
error capture for the self-healing loop (e.g. Exit Code 137 = OOM).
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    status: str  # success | failed | timeout
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    command: str = ""
    error: str | None = None
    classified: str | None = None  # oom | timeout | logic | resource | unknown

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "command": self.command,
            "error": self.error,
            "classified": self.classified,
        }


def classify_error(returncode: int | None, stderr: str = "") -> str:
    """Map tool failures to recovery categories for self-healing."""
    text = (stderr or "").lower()
    if returncode == 137 or "killed" in text or "cannot allocate memory" in text or "out of memory" in text:
        return "oom"
    if returncode in {126, 127} or "command not found" in text or (
        "no such file or directory" in text and ("bin/" in text or "executable" in text)
    ):
        return "missing_binary"
    if (
        "exec format error" in text
        or "wrong architecture" in text
        or "mach-o" in text
        or "rosetta" in text
        or "platform" in text and "linux/amd64" in text
    ):
        return "arch_mismatch"
    if (
        "libstdc++" in text
        or "glibc" in text
        or "libc.so" in text
        or "error while loading shared libraries" in text
        or "dyld" in text
    ):
        return "missing_library"
    if returncode is None or "timed out" in text:
        return "timeout"
    if returncode != 0:
        if "permission" in text or "disk" in text or "no space" in text:
            return "resource"
        if "conda" in text and ("not found" in text or "environment" in text):
            return "missing_binary"
        # DB / index problems (Kraken2, Bowtie, HUMAnN, …)
        if any(
            k in text
            for k in (
                "database not found",
                "db not found",
                "index not found",
                "cannot find taxonomy",
                "hash.k2d",
                "opts.k2d",
                "please download",
                "database directory",
            )
        ):
            return "missing_db"
        if "no such file or directory" in text or "file not found" in text or "cannot open" in text:
            return "missing_file"
        return "logic"
    return "unknown"


class LinuxBioToolRunner:
    """Execute bioinformatics commands via conda-run isolation or raw shell."""

    def __init__(
        self,
        conda_env: str | None = "metagenomics",
        use_conda: bool = True,
        default_timeout: int = 3600,
        env: dict[str, str] | None = None,
    ):
        self.conda_env = conda_env
        self.use_conda = use_conda and bool(conda_env)
        self.default_timeout = default_timeout
        self.env = {**os.environ, **(env or {})}

    def run_command(self, cmd: str | list[str], timeout: int | None = None, check: bool = False) -> CommandResult:
        if isinstance(cmd, list):
            display = " ".join(shlex.quote(c) for c in cmd)
            argv = cmd
        else:
            display = cmd
            argv = shlex.split(cmd)

        if self.use_conda and self.conda_env:
            full_argv = ["conda", "run", "-n", self.conda_env, "--no-capture-output", *argv]
            full_display = f"conda run -n {self.conda_env} {display}"
        else:
            full_argv = argv
            full_display = display

        logger.info("[Executing Command]: %s", full_display)
        try:
            result = subprocess.run(
                full_argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout or self.default_timeout,
                env=self.env,
                check=False,
            )
            if result.returncode != 0:
                classified = classify_error(result.returncode, result.stderr)
                logger.error("[Tool Error rc=%s classified=%s]: %s", result.returncode, classified, result.stderr[-2000:])
                out = CommandResult(
                    status="failed",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    returncode=result.returncode,
                    command=full_display,
                    error=result.stderr or f"exit {result.returncode}",
                    classified=classified,
                )
                if check:
                    raise RuntimeError(out.error)
                return out
            return CommandResult(
                status="success",
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=0,
                command=full_display,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                status="timeout",
                command=full_display,
                error=f"Command timed out after {timeout or self.default_timeout}s",
                classified="timeout",
                stdout=(exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                stderr=(exc.stderr or b"").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            )
        except FileNotFoundError as exc:
            return CommandResult(
                status="failed",
                command=full_display,
                error=str(exc),
                classified="missing_binary",
                returncode=127,
            )


# Convenience: Kraken2 species profiling with /dev/shm-friendly default DB path
def run_kraken2_species_profiling(
    fastq_1: str,
    fastq_2: str | None = None,
    db_path: str = "/dev/shm/kraken2_db",
    threads: int = 32,
    conda_env: str = "kraken2_env",
    report: str = "kraken_report.txt",
) -> dict[str, Any]:
    runner = LinuxBioToolRunner(conda_env=conda_env)
    if fastq_2:
        cmd = (
            f"kraken2 --db {shlex.quote(db_path)} --threads {threads} "
            f"--paired {shlex.quote(fastq_1)} {shlex.quote(fastq_2)} --report {shlex.quote(report)}"
        )
    else:
        cmd = (
            f"kraken2 --db {shlex.quote(db_path)} --threads {threads} "
            f"{shlex.quote(fastq_1)} --report {shlex.quote(report)}"
        )
    return runner.run_command(cmd).to_dict()
