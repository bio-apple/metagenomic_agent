"""Self-contained tool execution context (no coupling to external repos)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from metagenomic_agent.tools.docker_runner import docker_run, run_command

ExecMode = Literal["mock", "local", "docker"]


# Standard public images — not tied to any private project image
DEFAULT_IMAGES: dict[str, str] = {
    "fastp": "quay.io/biocontainers/fastp:0.23.4--h5f740d0_0",
    "bowtie2": "quay.io/biocontainers/bowtie2:2.5.3--py39hd2f008b_0",
    "kraken2": "quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0",
    "bracken": "quay.io/biocontainers/bracken:2.9--py39h3d4b393_0",
    "metaphlan": "quay.io/biocontainers/metaphlan:4.1.0--pyhca03a8a_0",
    "megahit": "quay.io/biocontainers/megahit:1.2.9--h43eeafb_4",
    "diamond": "quay.io/biocontainers/diamond:2.1.9--h43eeafb_0",
}


@dataclass
class ToolContext:
    mode: ExecMode
    outdir: Path
    threads: int = 8
    images: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_IMAGES))
    paths: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: dict[str, Any], outdir: str | Path, mode: str | None = None) -> ToolContext:
        raw_mode = mode or config.get("mode", "mock")
        # Map legacy "docker" to docker; allow explicit "local"
        if raw_mode not in {"mock", "local", "docker"}:
            raw_mode = "mock"
        docker_cfg = config.get("docker", {})
        images = dict(DEFAULT_IMAGES)
        images.update(docker_cfg.get("images") or {})
        # Optional single fallback image override (generic, not project-specific)
        if docker_cfg.get("default_image"):
            for k in list(images):
                images.setdefault(k, docker_cfg["default_image"])
        return cls(
            mode=raw_mode,  # type: ignore[arg-type]
            outdir=Path(outdir),
            threads=int(docker_cfg.get("threads", 8)),
            images=images,
            paths=dict(config.get("paths") or {}),
            extra={},
        )

    def which(self, binary: str) -> str | None:
        return shutil.which(binary)

    def run_local(self, argv: list[str], check: bool = True):
        return run_command(argv, check=check)

    def run_docker(self, tool: str, inner_cmd: str, volumes: dict[str, str], check: bool = True):
        image = self.images.get(tool) or self.images.get("fastp")
        if not image:
            raise RuntimeError(f"No docker image configured for tool '{tool}'")
        return docker_run(image, inner_cmd, volumes, check=check)
