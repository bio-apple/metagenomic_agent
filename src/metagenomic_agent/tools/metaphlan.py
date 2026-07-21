"""MetaPhlAn4 marker-based taxonomic profiling."""

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
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock":
        return mock_tools.write_taxonomy(outdir, sample_id, "metaphlan")

    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"]
    in_dir = str(Path(r1).parent)
    outdir.mkdir(parents=True, exist_ok=True)
    inner = (
        "export PATH=/opt/conda/envs/metaphlan/bin/:$PATH && "
        f"metaphlan /raw_data/{Path(r1).name} --input_type fastq "
        f"--nproc 8 -o /outdir/{sample_id}.metaphlan.txt"
    )
    docker_run(docker_image, inner, {in_dir: "/raw_data/", str(outdir): "/outdir/"})
    return {
        "metaphlan_abundance": str(outdir / f"{sample_id}.metaphlan.txt"),
        "top_genera": [],
        "classification_rate": 0.6,
    }
