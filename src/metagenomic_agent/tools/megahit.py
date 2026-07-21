"""MEGAHIT assembly wrapper."""

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

    if ctx.mode == "mock":
        return mock_tools.write_assembly(outdir, sample_id)

    r1 = Path(upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"])
    r2_raw = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2")
    r2 = Path(r2_raw) if r2_raw else None
    outdir.mkdir(parents=True, exist_ok=True)
    asm_dir = outdir / f"{sample_id}_megahit"

    if ctx.mode == "local" and ctx.which("megahit"):
        argv = ["megahit", "-1", str(r1), "-o", str(asm_dir), "--out-prefix", sample_id]
        if r2:
            argv.extend(["-2", str(r2)])
        ctx.run_local(argv)
    else:
        vols = {str(r1.parent): "/data", str(outdir): "/outdir"}
        pe = f"-1 /data/{r1.name}" + (f" -2 /data/{r2.name}" if r2 else "")
        inner = f"megahit {pe} -o /outdir/{asm_dir.name} --out-prefix {sample_id}"
        ctx.run_docker("megahit", inner, vols)

    contigs = asm_dir / "final.contigs.fa"
    return {
        "contigs": str(contigs),
        "bins_dir": str(outdir / "bins"),
        "gtdb_summary": None,
        "n_bins": 0,
    }
