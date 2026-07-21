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

    classification_rate = 0.6
    unclassified_fraction = 0.4
    if out.exists():
        try:
            # MetaPhlAn relative abundance; UNCLASSIFIED / UNKNOWN lines if present
            total = 0.0
            uncl = 0.0
            for line in out.read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                try:
                    val = float(parts[-1])
                except ValueError:
                    continue
                total += val
                name = parts[0].lower()
                if "unclassified" in name or "unknown" in name or name.endswith("|t__"):
                    uncl += val
            if total > 0:
                unclassified_fraction = min(1.0, uncl / total) if uncl else max(0.0, 1.0 - min(1.0, total / 100.0))
                classification_rate = max(0.0, 1.0 - unclassified_fraction)
        except OSError:
            pass
    return {
        "metaphlan_abundance": str(out),
        "top_genera": [],
        "classification_rate": classification_rate,
        "unclassified_fraction": unclassified_fraction,
    }
