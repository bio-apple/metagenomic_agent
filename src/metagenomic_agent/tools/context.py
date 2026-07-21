"""Self-contained tool execution context with Linux production modes."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from metagenomic_agent.tools.docker_runner import docker_run, run_command
from metagenomic_agent.tools.linux_runner import CommandResult

ExecMode = Literal["mock", "local", "conda", "docker", "apptainer"]


# BioContainers (quay.io/biocontainers) — pin tags for reproducibility
DEFAULT_IMAGES: dict[str, str] = {
    "fastp": "quay.io/biocontainers/fastp:0.23.4--h5f740d0_0",
    "fastqc": "quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0",
    "trimmomatic": "quay.io/biocontainers/trimmomatic:0.39--hdfd78af_2",
    "bowtie2": "quay.io/biocontainers/bowtie2:2.5.3--py39hd2f008b_0",
    "kneaddata": "quay.io/biocontainers/kneaddata:0.12.0--pyhdfd78af_1",
    "kraken2": "quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0",
    "bracken": "quay.io/biocontainers/bracken:2.9--py39h3d4b393_0",
    "metaphlan": "quay.io/biocontainers/metaphlan:4.1.0--pyhca03a8a_0",
    "megahit": "quay.io/biocontainers/megahit:1.2.9--h43eeafb_4",
    "spades": "quay.io/biocontainers/spades:3.15.5--h95f258a_1",
    "metaspades": "quay.io/biocontainers/spades:3.15.5--h95f258a_1",
    "metabat2": "quay.io/biocontainers/metabat2:2.15--h4ac6f70_1",
    "maxbin2": "quay.io/biocontainers/maxbin2:2.2.7--hdbdd923_5",
    "checkm2": "quay.io/biocontainers/checkm2:1.0.2--pyh7cba7a3_0",
    "gtdbtk": "quay.io/biocontainers/gtdbtk:2.4.0--pyhdfd78af_1",
    "bakta": "quay.io/biocontainers/bakta:1.9.3--pyhdfd78af_0",
    "humann": "quay.io/biocontainers/humann:3.8--pyhdfd78af_0",
    "humann3": "quay.io/biocontainers/humann:3.8--pyhdfd78af_0",
    "diamond": "quay.io/biocontainers/diamond:2.1.9--h43eeafb_0",
    "concoct": "quay.io/biocontainers/concoct:1.1.0--py311h245ed42_2",
    "rgi": "quay.io/biocontainers/rgi:6.0.3--pyha8f3691_0",
    "deeparg": "quay.io/biocontainers/deeparg:1.0.2--pyh7cba7a3_0",
    "virsorter2": "quay.io/biocontainers/virsorter:2.2.4--pyhdfd78af_1",
    "checkv": "quay.io/biocontainers/checkv:1.0.3--pyhdfd78af_0",
    "centrifuge": "quay.io/biocontainers/centrifuge:1.0.4.2--hdcf5f25_0",
    "resfinder": "quay.io/biocontainers/resfinder:4.4.2--pyhdfd78af_0",
    "amrfinderplus": "quay.io/biocontainers/ncbi-amrfinderplus:3.12.8--h283d622_0",
    "multiqc": "quay.io/biocontainers/multiqc:1.21--pyhdfd78af_0",
}

DEFAULT_CONDA_ENVS: dict[str, str] = {
    "fastp": "metagenomics",
    "bowtie2": "metagenomics",
    "kneaddata": "metagenomics",
    "kraken2": "kraken2_env",
    "bracken": "kraken2_env",
    "metaphlan": "metagenomics",
    "megahit": "metagenomics",
    "metaspades": "metagenomics",
    "metabat2": "metagenomics",
    "maxbin2": "metagenomics",
    "checkm2": "metagenomics",
    "gtdbtk": "gtdbtk",
    "diamond": "metagenomics",
}


@dataclass
class ToolContext:
    mode: ExecMode
    outdir: Path
    threads: int = 8
    memory_gb: int = 32
    images: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_IMAGES))
    conda_envs: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CONDA_ENVS))
    paths: dict[str, str] = field(default_factory=dict)
    prefer_shm: bool = True
    last_result: CommandResult | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: dict[str, Any], outdir: str | Path, mode: str | None = None) -> ToolContext:
        raw_mode = mode or config.get("mode", "mock")
        if raw_mode == "singularity":
            raw_mode = "apptainer"
        if raw_mode not in {"mock", "local", "conda", "docker", "apptainer"}:
            raw_mode = "mock"
        linux_cfg = config.get("linux", {})
        docker_cfg = config.get("docker", {})
        images = dict(DEFAULT_IMAGES)
        images.update(docker_cfg.get("images") or {})
        conda_envs = dict(DEFAULT_CONDA_ENVS)
        conda_envs.update(linux_cfg.get("conda_envs") or {})
        paths = dict(config.get("paths") or {})
        shm = linux_cfg.get("shm_db_root", "/dev/shm")
        if linux_cfg.get("prefer_shm", True) and Path(shm).exists():
            for key in ("kraken2_db", "gtdb", "host_index"):
                shm_candidate = Path(shm) / Path(paths.get(key, key)).name
                if shm_candidate.exists() and (
                    any(shm_candidate.iterdir()) if shm_candidate.is_dir() else shm_candidate.exists()
                ):
                    paths[key] = str(shm_candidate)
        return cls(
            mode=raw_mode,  # type: ignore[arg-type]
            outdir=Path(outdir),
            threads=int(docker_cfg.get("threads") or linux_cfg.get("threads") or 8),
            memory_gb=int(linux_cfg.get("memory_gb", 32)),
            images=images,
            conda_envs=conda_envs,
            paths=paths,
            prefer_shm=bool(linux_cfg.get("prefer_shm", True)),
            extra={"linux": linux_cfg, "sandbox": config.get("sandbox") or {}, "config": config},
        )

    def which(self, binary: str) -> str | None:
        return shutil.which(binary)

    def resolve_db(self, key: str, default: str = "") -> str:
        return (self.paths.get(key) or default or "").strip()

    def run_local(self, argv: list[str], check: bool = True):
        return run_command(argv, check=check)

    def run_docker(self, tool: str, inner_cmd: str, volumes: dict[str, str], check: bool = True):
        """Run in Docker or Apptainer/Singularity via sandbox (BioContainers images).

        Historically named run_docker; when mode=apptainer the call is routed to
        Apptainer so tool wrappers do not bypass HPC container runtimes.
        """
        import shlex

        from metagenomic_agent.tools.docker_runner import RunResult

        if self.mode in {"docker", "apptainer"}:
            argv = shlex.split(inner_cmd) if isinstance(inner_cmd, str) else list(inner_cmd)
            cr = self.run_tool(tool, argv, check=False, volumes=volumes)
            ok = cr.status == "success"
            if check and not ok:
                raise RuntimeError(cr.error or cr.stderr or f"{tool} failed")
            return RunResult(
                ok=ok,
                returncode=cr.returncode,
                stdout=cr.stdout,
                stderr=cr.stderr,
                command=cr.command,
            )

        # Legacy direct docker path (local/conda callers that still invoke run_docker)
        image = self.images.get(tool) or self.images.get("fastp")
        if not image:
            raise RuntimeError(f"No BioContainers image configured for tool '{tool}'")
        sandbox_cfg = (self.extra or {}).get("sandbox") or {}
        platform = sandbox_cfg.get("platform") or (self.extra.get("config") or {}).get("docker", {}).get("platform")
        return docker_run(
            image,
            inner_cmd,
            volumes,
            check=check,
            platform=platform if platform and platform != "auto" else None,
            memory_gb=self.memory_gb,
            cpus=self.threads,
        )

    def run_tool(
        self,
        tool: str,
        argv: list[str],
        timeout: int | None = None,
        check: bool = False,
        volumes: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run via MCP-style sandbox (container preferred) or conda/local."""
        from metagenomic_agent.tools.sandbox import ToolCallRequest, sandbox_from_config

        cfg = dict((self.extra or {}).get("config") or {})
        cfg.setdefault("mode", self.mode)
        cfg.setdefault("docker", {})["images"] = self.images
        cfg.setdefault("docker", {})["threads"] = self.threads
        cfg.setdefault("linux", {})["memory_gb"] = self.memory_gb
        cfg.setdefault("linux", {})["conda_envs"] = self.conda_envs
        if "sandbox" not in cfg:
            cfg["sandbox"] = dict((self.extra or {}).get("sandbox") or {})

        # Prefer container backends when mode is docker/apptainer
        executor = sandbox_from_config(cfg)
        # Ensure images known to executor
        executor.images = {**executor.images, **self.images}
        executor.conda_envs = {**executor.conda_envs, **self.conda_envs}

        req = ToolCallRequest(
            tool=tool,
            argv=argv,
            volumes=volumes or {str(self.outdir.resolve()): "/work"},
            threads=self.threads,
            memory_gb=self.memory_gb,
            timeout_s=timeout or 3600,
            platform=(cfg.get("sandbox") or {}).get("platform", "auto"),
            image=self.images.get(tool),
            conda_env=self.conda_envs.get(tool),
            check=check,
            workdir="/work" if volumes or self.mode in {"docker", "apptainer"} else None,
        )
        resp = executor.execute(req)
        result = CommandResult(
            status="success" if resp.ok else "failed",
            stdout=resp.stdout,
            stderr=resp.stderr,
            returncode=resp.returncode,
            command=resp.command,
            error=None if resp.ok else (resp.user_message or resp.stderr),
            classified=resp.classified,
        )
        self.last_result = result
        self.extra["last_tool_call"] = resp.model_dump()
        if check and not resp.ok:
            raise RuntimeError(resp.user_message or resp.stderr or f"{tool} failed")
        return result
