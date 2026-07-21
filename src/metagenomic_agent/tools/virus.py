"""Viral discovery: VirSorter2 + CheckV (mock-friendly)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools.context import ToolContext


def run_virsorter2(contigs: str, outdir: Path, ctx: ToolContext, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    summary = outdir / f"{sample_id}.virsorter2.tsv"
    if ctx.mode == "mock":
        summary.write_text(
            "seqname\tdsDNAphage\tssDNA\tmax_score\tmax_score_group\n"
            f"{sample_id}_contig_1\t0.9\t0.1\t0.9\tdsDNAphage\n",
            encoding="utf-8",
        )
        fa = outdir / f"{sample_id}.viral.fa"
        fa.write_text(f">{sample_id}_viral_1\n{'ATGC' * 200}\n", encoding="utf-8")
        return {
            "virsorter2_tsv": str(summary),
            "viral_fasta": str(fa),
            "n_viral": 1,
            "tool": "virsorter2",
        }

    argv = [
        "virsorter",
        "run",
        "-w",
        str(outdir / "vs2"),
        "-i",
        contigs,
        "--min-length",
        "3000",
        "-j",
        str(ctx.threads),
        "all",
    ]
    if ctx.mode in {"local", "conda"}:
        ctx.run_tool("virsorter2", argv, check=False)
    else:
        vols = {str(Path(contigs).parent): "/data", str(outdir): "/outdir"}
        inner = (
            f"virsorter run -w /outdir/vs2 -i /data/{Path(contigs).name} "
            f"--min-length 3000 -j {ctx.threads} all"
        )
        ctx.run_docker("virsorter2", inner, vols)
    if not summary.exists():
        summary.write_text("seqname\tmax_score\tmax_score_group\n", encoding="utf-8")
    return {"virsorter2_tsv": str(summary), "n_viral": max(0, len(summary.read_text().splitlines()) - 1), "tool": "virsorter2"}


def run_checkv(viral_fasta: str, outdir: Path, ctx: ToolContext, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    quality = outdir / f"{sample_id}.checkv_quality.tsv"
    if ctx.mode == "mock":
        quality.write_text(
            "contig_id\tcontig_length\tprovirus\tcheckv_quality\n"
            f"{sample_id}_viral_1\t8000\tNo\tMedium-quality\n",
            encoding="utf-8",
        )
        return {"checkv_tsv": str(quality), "n_contigs": 1, "tool": "checkv"}

    argv = ["checkv", "end_to_end", viral_fasta, str(outdir / "checkv_out"), "-t", str(ctx.threads)]
    if ctx.mode in {"local", "conda"}:
        ctx.run_tool("checkv", argv, check=False)
    else:
        vols = {str(Path(viral_fasta).parent): "/data", str(outdir): "/outdir"}
        inner = f"checkv end_to_end /data/{Path(viral_fasta).name} /outdir/checkv_out -t {ctx.threads}"
        ctx.run_docker("checkv", inner, vols)
    if not quality.exists():
        cand = outdir / "checkv_out" / "quality_summary.tsv"
        if cand.exists():
            quality.write_text(cand.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            quality.write_text("contig_id\tcheckv_quality\n", encoding="utf-8")
    return {"checkv_tsv": str(quality), "n_contigs": max(0, len(quality.read_text().splitlines()) - 1), "tool": "checkv"}


def run_virus_suite(contigs: str, outdir: Path, ctx: ToolContext, sample_id: str) -> dict[str, Any]:
    vs = run_virsorter2(contigs, outdir / "virsorter2", ctx, sample_id)
    viral_fa = vs.get("viral_fasta")
    if not viral_fa or not Path(viral_fa).exists():
        # synthesize empty for checkv skip
        return {**vs, "checkv": {"skipped": True, "reason": "no viral fasta"}}
    cv = run_checkv(str(viral_fa), outdir / "checkv", ctx, sample_id)
    return {**vs, "checkv": cv}
