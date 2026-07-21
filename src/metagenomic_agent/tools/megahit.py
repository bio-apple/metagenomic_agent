"""MEGAHIT assembly + MetaBAT2 binning + GTDB-Tk (MVP wrappers)."""

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
        return mock_tools.write_assembly(outdir, sample_id)

    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"]
    r2 = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2")
    in_dir = str(Path(r1).parent)
    outdir.mkdir(parents=True, exist_ok=True)
    pe = f"-1 /raw_data/{Path(r1).name}"
    if r2:
        pe += f" -2 /raw_data/{Path(r2).name}"
    inner = (
        "export PATH=/opt/conda/envs/megahit/bin/:$PATH && "
        f"megahit {pe} -o /outdir/{sample_id}_megahit --out-prefix {sample_id}"
    )
    docker_run(docker_image, inner, {in_dir: "/raw_data/", str(outdir): "/outdir/"})
    return {
        "contigs": str(outdir / f"{sample_id}_megahit" / "final.contigs.fa"),
        "bins_dir": str(outdir / "bins"),
        "gtdb_summary": None,
        "n_bins": 0,
    }
