"""Kraken2 + Bracken taxonomic classification."""

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
    kraken_db: str = "",
    read_length: int = 150,
    confidence: float = 0.05,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock" or not kraken_db:
        return mock_tools.write_taxonomy(outdir, sample_id, "kraken2")

    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"]
    r2 = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2")
    in_dir = str(Path(r1).parent)
    outdir.mkdir(parents=True, exist_ok=True)
    paired = (
        f" --paired /raw_data/{Path(r1).name} /raw_data/{Path(r2).name}"
        if r2
        else f" /raw_data/{Path(r1).name}"
    )
    inner = (
        "export PATH=/opt/conda/envs/kraken2/bin/:$PATH && "
        f"kraken2 --db /ref/ --threads 8 --confidence {confidence} "
        f"--output /outdir/{sample_id}.txt --report /outdir/{sample_id}.report.txt"
        f"{paired} && "
        f"bracken -d /ref/ -i /outdir/{sample_id}.report.txt -r {read_length} "
        f"-o /outdir/{sample_id}.bracken -w /outdir/{sample_id}.breport -t 10"
    )
    docker_run(
        docker_image,
        inner,
        {in_dir: "/raw_data/", kraken_db: "/ref/", str(outdir): "/outdir/"},
    )
    return {
        "kraken2_report": str(outdir / f"{sample_id}.report.txt"),
        "kraken2_abundance": str(outdir / f"{sample_id}.bracken"),
        "top_genera": [],
        "classification_rate": 0.5,
    }
