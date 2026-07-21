"""Host removal: Bowtie2 (HG38) and optional Kneaddata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.context import ToolContext


def run(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext | None = None,
    **legacy: Any,
) -> dict[str, Any]:
    ctx = ctx or ToolContext(mode=legacy.get("mode", "mock"), outdir=outdir)
    sample_id = sample["sample_id"]
    host_index = ctx.resolve_db("host_index") or (legacy.get("host_index") or "").strip()
    method = (legacy.get("method") or ctx.extra.get("linux", {}).get("host_method") or "bowtie2").lower()

    if ctx.mode == "mock" or not host_index:
        return mock_tools.write_host_filter(outdir, sample_id, upstream)

    if method == "kneaddata":
        return _run_kneaddata(sample, upstream, outdir, ctx, host_index)
    return _run_bowtie2(sample, upstream, outdir, ctx, host_index)


def _run_bowtie2(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext,
    host_index: str,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    r1 = Path(upstream.get("clean_r1") or sample["r1"])
    r2_raw = upstream.get("clean_r2") or sample.get("r2")
    r2 = Path(r2_raw) if r2_raw else None
    outdir.mkdir(parents=True, exist_ok=True)

    index_prefix = host_index
    if Path(host_index).is_dir():
        index_prefix = str(Path(host_index) / "genome")

    sam = outdir / f"{sample_id}.sam"
    unconc = outdir / f"{sample_id}.nonhost.fastq"
    argv = [
        "bowtie2",
        "-x",
        index_prefix,
        "-1",
        str(r1),
        "-S",
        str(sam),
        "--un-conc",
        str(unconc),
        "--threads",
        str(ctx.threads),
    ]
    if r2:
        argv = [
            "bowtie2",
            "-x",
            index_prefix,
            "-1",
            str(r1),
            "-2",
            str(r2),
            "-S",
            str(sam),
            "--un-conc",
            str(unconc),
            "--threads",
            str(ctx.threads),
        ]

    if ctx.mode in {"local", "conda"}:
        ctx.run_tool("bowtie2", argv, check=False)
    else:
        idx_dir = str(Path(index_prefix).parent)
        vols = {str(r1.parent): "/data", idx_dir: "/ref", str(outdir): "/outdir"}
        pe = f"-1 /data/{r1.name}" + (f" -2 /data/{r2.name}" if r2 else "")
        inner = (
            f"bowtie2 -x /ref/{Path(index_prefix).name} {pe} "
            f"-S /outdir/{sam.name} --un-conc /outdir/{unconc.name} --threads {ctx.threads}"
        )
        ctx.run_docker("bowtie2", inner, vols)

    return {
        **upstream,
        "nonhost_r1": str(outdir / f"{sample_id}.nonhost.1.fastq"),
        "nonhost_r2": str(outdir / f"{sample_id}.nonhost.2.fastq") if r2 else None,
        "host_fraction": 0.1,
        "host_method": "bowtie2",
    }


def _run_kneaddata(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext,
    host_index: str,
) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    r1 = Path(upstream.get("clean_r1") or sample["r1"])
    r2_raw = upstream.get("clean_r2") or sample.get("r2")
    r2 = Path(r2_raw) if r2_raw else None
    outdir.mkdir(parents=True, exist_ok=True)

    argv = [
        "kneaddata",
        "--input1",
        str(r1),
        "--reference-db",
        host_index,
        "--output",
        str(outdir),
        "--threads",
        str(ctx.threads),
        "--output-prefix",
        sample_id,
    ]
    if r2:
        argv.extend(["--input2", str(r2)])

    if ctx.mode in {"local", "conda"}:
        ctx.run_tool("kneaddata", argv, check=False)
    else:
        vols = {str(r1.parent): "/data", host_index: "/ref", str(outdir): "/outdir"}
        pe = f"--input1 /data/{r1.name}" + (f" --input2 /data/{r2.name}" if r2 else "")
        inner = (
            f"kneaddata {pe} --reference-db /ref --output /outdir "
            f"--threads {ctx.threads} --output-prefix {sample_id}"
        )
        ctx.run_docker("kneaddata", inner, vols)

    return {
        **upstream,
        "nonhost_r1": str(outdir / f"{sample_id}_paired_1.fastq"),
        "nonhost_r2": str(outdir / f"{sample_id}_paired_2.fastq") if r2 else None,
        "host_fraction": 0.1,
        "host_method": "kneaddata",
    }
