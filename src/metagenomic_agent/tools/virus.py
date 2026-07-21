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


def run_genomad(contigs: str, outdir: Path, ctx: ToolContext, sample_id: str) -> dict[str, Any]:
    """geNomad virus/plasmid identification (benchmark-informed primary caller)."""
    outdir.mkdir(parents=True, exist_ok=True)
    summary = outdir / f"{sample_id}.genomad.tsv"
    fa = outdir / f"{sample_id}.genomad.viral.fa"
    if ctx.mode == "mock":
        summary.write_text(
            "seq_name\tvirus_score\tplasmid_score\n"
            f"{sample_id}_contig_1\t0.92\t0.05\n",
            encoding="utf-8",
        )
        fa.write_text(f">{sample_id}_genomad_viral_1\n{'ATGC' * 200}\n", encoding="utf-8")
        return {
            "genomad_tsv": str(summary),
            "viral_fasta": str(fa),
            "n_viral": 1,
            "tool": "genomad",
        }

    if ctx.mode in {"local", "conda"} and ctx.which("genomad"):
        ctx.run_tool(
            "genomad",
            ["genomad", "end-to-end", contigs, str(outdir / "genomad_out"), "--threads", str(ctx.threads)],
            check=False,
        )
    else:
        vols = {str(Path(contigs).parent): "/data", str(outdir): "/outdir"}
        inner = (
            f"genomad end-to-end /data/{Path(contigs).name} /outdir/genomad_out "
            f"--threads {ctx.threads}"
        )
        ctx.run_docker("genomad", inner, vols)
    if not summary.exists():
        summary.write_text("seq_name\tvirus_score\n", encoding="utf-8")
    if not fa.exists():
        fa.write_text("", encoding="utf-8")
    n = max(0, len(summary.read_text(encoding="utf-8").splitlines()) - 1)
    return {"genomad_tsv": str(summary), "viral_fasta": str(fa), "n_viral": n, "tool": "genomad"}


def run_virus_suite(contigs: str, outdir: Path, ctx: ToolContext, sample_id: str) -> dict[str, Any]:
    """Multi-tool virus ID (VirSorter2 + geNomad) → CheckV — Wu et al. 2024 informed."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    vs = run_virsorter2(contigs, outdir / "virsorter2", ctx, sample_id)
    gm = run_genomad(contigs, outdir / "genomad", ctx, sample_id)
    # Prefer union of viral fastas for CheckV
    viral_fa = vs.get("viral_fasta") or gm.get("viral_fasta")
    if gm.get("viral_fasta") and Path(str(gm["viral_fasta"])).exists() and Path(str(gm["viral_fasta"])).stat().st_size > 0:
        if vs.get("viral_fasta") and Path(str(vs["viral_fasta"])).exists():
            merged = outdir / f"{sample_id}.viral_merged.fa"
            parts = []
            for p in (vs["viral_fasta"], gm["viral_fasta"]):
                parts.append(Path(p).read_text(encoding="utf-8", errors="ignore"))
            merged.write_text("".join(parts), encoding="utf-8")
            viral_fa = str(merged)
        else:
            viral_fa = gm["viral_fasta"]
    consensus = {
        "callers": ["virsorter2", "genomad"],
        "n_virsorter2": vs.get("n_viral", 0),
        "n_genomad": gm.get("n_viral", 0),
        "n_union_proxy": int(vs.get("n_viral") or 0) + int(gm.get("n_viral") or 0),
        "note": "Multi-caller suite; biome-specific performance varies (Wu et al. 2024).",
    }
    (outdir / "virus_callers.json").write_text(
        __import__("json").dumps(consensus, indent=2), encoding="utf-8"
    )
    if not viral_fa or not Path(viral_fa).exists() or Path(viral_fa).stat().st_size == 0:
        return {**vs, "genomad": gm, "checkv": {"skipped": True, "reason": "no viral fasta"}, "consensus": consensus}
    cv = run_checkv(str(viral_fa), outdir / "checkv", ctx, sample_id)
    return {**vs, "genomad": gm, "checkv": cv, "consensus": consensus}
