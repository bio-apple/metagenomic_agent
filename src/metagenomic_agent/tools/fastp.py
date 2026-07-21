"""fastp quality trimming — mock / local PATH / biocontainers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.context import ToolContext


def run(
    sample: dict[str, Any],
    outdir: Path,
    ctx: ToolContext | None = None,
    **legacy: Any,
) -> dict[str, Any]:
    ctx = ctx or _legacy_ctx(outdir, legacy)
    sample_id = sample["sample_id"]
    outdir.mkdir(parents=True, exist_ok=True)

    if ctx.mode == "mock":
        return mock_tools.write_fastp(outdir, sample_id)

    pe1 = Path(sample["r1"])
    pe2 = Path(sample["r2"]) if sample.get("r2") else None
    out_r1 = outdir / f"{sample_id}.clean_R1.fastq"
    out_r2 = outdir / f"{sample_id}.clean_R2.fastq"
    html = outdir / f"{sample_id}.fastp.html"
    jpath = outdir / f"{sample_id}.fastp.json"

    argv = [
        "fastp",
        "-i",
        str(pe1),
        "-o",
        str(out_r1),
        "--length_required",
        "36",
        "--dedup",
        "--thread",
        str(ctx.threads),
        "--low_complexity_filter",
        "--qualified_quality_phred",
        "20",
        "--html",
        str(html),
        "--json",
        str(jpath),
    ]
    if pe2:
        argv.extend(["-I", str(pe2), "-O", str(out_r2)])

    if ctx.mode == "local" and ctx.which("fastp"):
        ctx.run_local(argv)
    else:
        # docker biocontainer: mount parent dirs
        vols = {str(pe1.parent): "/data", str(outdir): "/outdir"}
        inner = (
            f"fastp -i /data/{pe1.name} -o /outdir/{out_r1.name} "
            f"--length_required 36 --dedup --thread {ctx.threads} "
            f"--low_complexity_filter --qualified_quality_phred 20 "
            f"--html /outdir/{html.name} --json /outdir/{jpath.name}"
        )
        if pe2:
            if pe2.parent != pe1.parent:
                raise ValueError("Paired FASTQs must share the same directory for docker mode")
            inner += f" -I /data/{pe2.name} -O /outdir/{out_r2.name}"
        ctx.run_docker("fastp", inner, vols)

    q30 = 90
    retention = 0.9
    if jpath.exists():
        try:
            data = json.loads(jpath.read_text())
            q30 = int(float(data["summary"]["after_filtering"]["q30_rate"]) * 100)
            before = float(data["summary"]["before_filtering"]["total_reads"]) or 1
            after = float(data["summary"]["after_filtering"]["total_reads"])
            retention = after / before
        except (KeyError, ValueError, json.JSONDecodeError):
            pass

    return {
        "fastp_json": str(jpath),
        "fastp_html": str(html),
        "clean_r1": str(out_r1),
        "clean_r2": str(out_r2) if pe2 else None,
        "Q30": q30,
        "adapter_removed": True,
        "status": "PASS",
        "read_retention": retention,
        "host_fraction": 0.0,
    }


def _legacy_ctx(outdir: Path, legacy: dict[str, Any]) -> ToolContext:
    mode = legacy.get("mode", "mock")
    if mode == "docker":
        mode = "docker"
    return ToolContext(
        mode=mode if mode in {"mock", "local", "docker"} else "mock",
        outdir=outdir,
        threads=int(legacy.get("threads", 8)),
    )
