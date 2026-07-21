"""MetaPhlAn marker-based taxonomic profiling."""

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
        return mock_tools.write_taxonomy(outdir, sample_id, "metaphlan")

    r1 = Path(upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"])
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{sample_id}.metaphlan.txt"

    if ctx.mode == "local" and ctx.which("metaphlan"):
        ctx.run_local(
            [
                "metaphlan",
                str(r1),
                "--input_type",
                "fastq",
                "--nproc",
                str(ctx.threads),
                "-o",
                str(out),
            ]
        )
    else:
        vols = {str(r1.parent): "/data", str(outdir): "/outdir"}
        inner = (
            f"metaphlan /data/{r1.name} --input_type fastq "
            f"--nproc {ctx.threads} -o /outdir/{out.name}"
        )
        ctx.run_docker("metaphlan", inner, vols)

    return {
        "metaphlan_abundance": str(out),
        "top_genera": [],
        "classification_rate": 0.6,
    }
