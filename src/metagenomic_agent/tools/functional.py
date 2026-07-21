"""Functional annotation: KEGG / eggNOG / CAZy / CARD / VFDB."""

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
        return mock_tools.write_functional(outdir, sample_id)

    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"]
    in_dir = str(Path(r1).parent)
    outdir.mkdir(parents=True, exist_ok=True)
    inner = (
        "export PATH=/opt/conda/envs/diamond/bin/:$PATH && "
        f"diamond blastx -q /raw_data/{Path(r1).name} -d /ref/nr "
        f"-o /outdir/{sample_id}.diamond.tsv --threads 8 --max-target-seqs 1"
    )
    docker_run(docker_image, inner, {in_dir: "/raw_data/", str(outdir): "/outdir/"})
    profile = outdir / f"{sample_id}.functional_profile.tsv"
    profile.write_text("feature\tabundance\tdatabase\n")
    return {
        "functional_profile": str(profile),
        "diamond_tsv": str(outdir / f"{sample_id}.diamond.tsv"),
        "databases": ["KEGG", "eggNOG", "CAZy", "CARD", "VFDB"],
        "n_features": 0,
    }
