"""Bioinformatics tool wrappers (mock or docker)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.docker_runner import docker_run


def run_fastp(
    sample: dict[str, Any],
    outdir: Path,
    mode: str,
    docker_image: str,
    threads: int = 8,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock":
        return mock_tools.write_mock_fastp(outdir, sample_id)

    pe1 = sample["r1"]
    pe2 = sample.get("r2")
    in_dir = str(Path(pe1).parent)
    out = str(outdir)
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
    docker_run(docker_image, inner, {in_dir: "/raw_data/", out: "/outdir/"})
    return {
        "fastp_json": str(outdir / f"{sample_id}.fastp.json"),
        "fastp_html": str(outdir / f"{sample_id}.fastp.html"),
        "clean_r1": str(outdir / f"{sample_id}.clean_R1.fastq"),
        "clean_r2": str(outdir / f"{sample_id}.clean_R2.fastq") if pe2 else None,
        "read_retention": 0.9,
        "host_fraction": 0.0,
    }


def run_host_filter(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    mode: str,
    docker_image: str,
    host_index: str,
    threads: int = 8,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock" or not host_index:
        return mock_tools.write_mock_host_filter(outdir, sample_id, upstream)

    r1 = upstream.get("clean_r1") or sample["r1"]
    r2 = upstream.get("clean_r2") or sample.get("r2")
    in_dir = str(Path(r1).parent)
    out = str(outdir)
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
        {in_dir: "/raw_data/", host_index: "/ref/", out: "/outdir/"},
    )
    return {
        **upstream,
        "nonhost_r1": str(outdir / f"{sample_id}.nonhost.1.fastq"),
        "nonhost_r2": str(outdir / f"{sample_id}.nonhost.2.fastq") if r2 else None,
        "host_fraction": 0.1,
    }


def run_kraken2(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    mode: str,
    docker_image: str,
    kraken_db: str,
    read_length: int = 150,
    confidence: float = 0.05,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock" or not kraken_db:
        return mock_tools.write_mock_taxonomy(outdir, sample_id, "kraken2")

    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"]
    r2 = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2")
    in_dir = str(Path(r1).parent)
    out = str(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paired = f" --paired /raw_data/{Path(r1).name} /raw_data/{Path(r2).name}" if r2 else f" /raw_data/{Path(r1).name}"
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
        {in_dir: "/raw_data/", kraken_db: "/ref/", out: "/outdir/"},
    )
    return {
        "kraken2_report": str(outdir / f"{sample_id}.report.txt"),
        "kraken2_abundance": str(outdir / f"{sample_id}.bracken"),
        "top_genera": [],
    }


def run_metaphlan(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    mode: str,
    docker_image: str,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock":
        return mock_tools.write_mock_taxonomy(outdir, sample_id, "metaphlan")

    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"]
    in_dir = str(Path(r1).parent)
    out = str(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    inner = (
        "export PATH=/opt/conda/envs/metaphlan/bin/:$PATH && "
        f"metaphlan /raw_data/{Path(r1).name} --input_type fastq "
        f"--nproc 8 -o /outdir/{sample_id}.metaphlan.txt"
    )
    docker_run(docker_image, inner, {in_dir: "/raw_data/", out: "/outdir/"})
    return {
        "metaphlan_abundance": str(outdir / f"{sample_id}.metaphlan.txt"),
        "top_genera": [],
    }


def run_diamond(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    mode: str,
    docker_image: str,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    if mode == "mock":
        return mock_tools.write_mock_functional(outdir, sample_id)

    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"]
    in_dir = str(Path(r1).parent)
    out = str(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    inner = (
        "export PATH=/opt/conda/envs/diamond/bin/:$PATH && "
        f"diamond blastx -q /raw_data/{Path(r1).name} -d /ref/nr -o /outdir/{sample_id}.diamond.tsv "
        "--threads 8 --max-target-seqs 1"
    )
    docker_run(docker_image, inner, {in_dir: "/raw_data/", out: "/outdir/"})
    return {"diamond_tsv": str(outdir / f"{sample_id}.diamond.tsv"), "n_hits": -1}
