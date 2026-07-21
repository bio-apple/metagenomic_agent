"""VAMB deep-learning binner wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools.context import ToolContext


def run_vamb(
    sample_id: str,
    contigs: str,
    outdir: Path,
    ctx: ToolContext,
) -> dict[str, Any]:
    """Run VAMB or write mock bins when tools are unavailable."""
    outdir.mkdir(parents=True, exist_ok=True)
    bins_dir = outdir / "vamb_bins"
    bins_dir.mkdir(parents=True, exist_ok=True)

    if ctx.mode == "mock":
        fa = bins_dir / f"{sample_id}.vamb.bin.1.fa"
        fa.write_text(f">vamb_{sample_id}_1\nACGTACGTACGT\n", encoding="utf-8")
        return {
            "vamb_bins_dir": str(bins_dir),
            "n_vamb_bins": 1,
            "binner": "vamb",
        }

    contig_path = Path(contigs)
    if ctx.mode in {"local", "conda"} and ctx.which("vamb"):
        argv = [
            "vamb",
            "--outdir",
            str(outdir / "vamb_run"),
            "--fasta",
            str(contig_path),
            "-o",
            "C",
        ]
        ctx.run_local(argv, check=False)
    else:
        vols = {str(contig_path.parent): "/data", str(outdir): "/outdir"}
        inner = f"vamb --outdir /outdir/vamb_run --fasta /data/{contig_path.name} -o C"
        ctx.run_docker("vamb", inner, vols)

    n = len(list(bins_dir.glob("*.fa"))) + len(list((outdir / "vamb_run").glob("**/*.fna")))
    return {"vamb_bins_dir": str(bins_dir), "n_vamb_bins": n, "binner": "vamb"}
