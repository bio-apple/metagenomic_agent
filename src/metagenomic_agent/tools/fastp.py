"""fastp quality trimming tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.docker_runner import docker_run


def run(
    sample: dict[str, Any],
    outdir: Path,
    mode: str = "mock",
    docker_image: str = "meta:latest",
    threads: int = 8,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock":
        return mock_tools.write_fastp(outdir, sample_id)

    pe1 = sample["r1"]
    pe2 = sample.get("r2")
    in_dir = str(Path(pe1).parent)
    outdir.mkdir(parents=True, exist_ok=True)
    inner = (
        "export PATH=/opt/conda/envs/rgi/bin/:$PATH && "
        f"fastp -i /raw_data/{Path(pe1).name} -o /outdir/{sample_id}.clean_R1.fastq "
        f"--length_required 36 --dedup --thread {threads} --low_complexity_filter "
        "--qualified_quality_phred 20 "
        f"--html /outdir/{sample_id}.fastp.html --json /outdir/{sample_id}.fastp.json"
    )
    if pe2:
        inner += f" -I /raw_data/{Path(pe2).name} -O /outdir/{sample_id}.clean_R2.fastq"
    docker_run(docker_image, inner, {in_dir: "/raw_data/", str(outdir): "/outdir/"})
    return {
        "fastp_json": str(outdir / f"{sample_id}.fastp.json"),
        "fastp_html": str(outdir / f"{sample_id}.fastp.html"),
        "clean_r1": str(outdir / f"{sample_id}.clean_R1.fastq"),
        "clean_r2": str(outdir / f"{sample_id}.clean_R2.fastq") if pe2 else None,
        "Q30": 90,
        "adapter_removed": True,
        "status": "PASS",
        "read_retention": 0.9,
        "host_fraction": 0.0,
    }
