"""Host DNA removal via Bowtie2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.docker_runner import docker_run


def run(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    mode: str = "mock",
    docker_image: str = "meta:latest",
    host_index: str = "",
    threads: int = 8,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock" or not host_index:
        return mock_tools.write_host_filter(outdir, sample_id, upstream)

    r1 = upstream.get("clean_r1") or sample["r1"]
    r2 = upstream.get("clean_r2") or sample.get("r2")
    in_dir = str(Path(r1).parent)
    outdir.mkdir(parents=True, exist_ok=True)
    inner = (
        "export PATH=/opt/conda/envs/bowtie2/bin/:$PATH && "
        f"bowtie2 -x /ref/genome -1 /raw_data/{Path(r1).name} "
        + (f"-2 /raw_data/{Path(r2).name} " if r2 else "")
        + f"-S /outdir/{sample_id}.sam --un-conc /outdir/{sample_id}.nonhost.fastq "
        f"--threads {threads}"
    )
    docker_run(
        docker_image,
        inner,
        {in_dir: "/raw_data/", host_index: "/ref/", str(outdir): "/outdir/"},
    )
    return {
        **upstream,
        "nonhost_r1": str(outdir / f"{sample_id}.nonhost.1.fastq"),
        "nonhost_r2": str(outdir / f"{sample_id}.nonhost.2.fastq") if r2 else None,
        "host_fraction": 0.1,
    }
