"""Flye assembler wrapper (long-read metagenomes)."""

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
    """Assemble long reads with Flye (--meta). Falls back to mock artifacts in mock mode."""
    ctx = ctx or ToolContext(mode=legacy.get("mode", "mock"), outdir=outdir)
    sample_id = sample["sample_id"]
    outdir.mkdir(parents=True, exist_ok=True)

    if ctx.mode == "mock":
        art = mock_tools.write_assembly(outdir, sample_id)
        art["assembler"] = "flye"
        return art

    reads = Path(
        upstream.get("nonhost_r1")
        or upstream.get("clean_r1")
        or sample.get("r1")
        or sample.get("reads")
        or ""
    )
    asm_dir = outdir / f"{sample_id}_flye"
    if ctx.mode in {"local", "conda"} and ctx.which("flye"):
        argv = [
            "flye",
            "--nano-raw",
            str(reads),
            "--out-dir",
            str(asm_dir),
            "--meta",
            "--threads",
            str(ctx.threads),
        ]
        result = ctx.run_local(argv, check=False)
        if getattr(result, "status", None) not in {None, "success"} and getattr(result, "returncode", 0) not in {
            0,
            None,
        }:
            raise RuntimeError(getattr(result, "error", None) or "Flye failed")
    else:
        vols = {str(reads.parent): "/data", str(outdir): "/outdir"}
        inner = (
            f"flye --nano-raw /data/{reads.name} --out-dir /outdir/{asm_dir.name} "
            f"--meta --threads {ctx.threads}"
        )
        ctx.run_docker("flye", inner, vols)

    contigs = asm_dir / "assembly.fasta"
    if not contigs.exists():
        contigs = asm_dir / "scaffolds.fasta"
    return {
        "contigs": str(contigs),
        "assembler": "flye",
        "assembly_dir": str(asm_dir),
        "n_bins": 0,
    }
