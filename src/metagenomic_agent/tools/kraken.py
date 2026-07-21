"""Kraken2 + Bracken taxonomic classification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.context import ToolContext


def _db_ready(path: str) -> bool:
    p = Path(path)
    if not path or not p.exists() or not p.is_dir():
        return False
    return any(x.name != ".gitkeep" for x in p.iterdir())


def run(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext | None = None,
    **legacy: Any,
) -> dict[str, Any]:
    ctx = ctx or ToolContext(mode=legacy.get("mode", "mock"), outdir=outdir)
    sample_id = sample["sample_id"]
    kraken_db = (ctx.paths.get("kraken2_db") or legacy.get("kraken_db") or "").strip()
    confidence = float(legacy.get("confidence", 0.05))
    read_length = int(legacy.get("read_length", sample.get("read_length_est", 150)))

    if ctx.mode == "mock" or not _db_ready(kraken_db):
        return mock_tools.write_taxonomy(outdir, sample_id, "kraken2")

    r1 = Path(upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"])
    r2_raw = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2")
    r2 = Path(r2_raw) if r2_raw else None
    outdir.mkdir(parents=True, exist_ok=True)

    out_txt = outdir / f"{sample_id}.txt"
    report = outdir / f"{sample_id}.report.txt"
    bracken = outdir / f"{sample_id}.bracken"
    breport = outdir / f"{sample_id}.breport"

    if ctx.mode == "local" and ctx.which("kraken2"):
        argv = [
            "kraken2",
            "--db",
            kraken_db,
            "--threads",
            str(ctx.threads),
            "--confidence",
            str(confidence),
            "--output",
            str(out_txt),
            "--report",
            str(report),
        ]
        if r2:
            argv.extend(["--paired", str(r1), str(r2)])
        else:
            argv.append(str(r1))
        ctx.run_local(argv)
        if ctx.which("bracken"):
            ctx.run_local(
                [
                    "bracken",
                    "-d",
                    kraken_db,
                    "-i",
                    str(report),
                    "-r",
                    str(read_length),
                    "-o",
                    str(bracken),
                    "-w",
                    str(breport),
                    "-t",
                    "10",
                ]
            )
    else:
        vols = {str(r1.parent): "/data", kraken_db: "/ref", str(outdir): "/outdir"}
        reads = f"--paired /data/{r1.name} /data/{r2.name}" if r2 else f"/data/{r1.name}"
        inner = (
            f"kraken2 --db /ref --threads {ctx.threads} --confidence {confidence} "
            f"--output /outdir/{out_txt.name} --report /outdir/{report.name} {reads}"
        )
        ctx.run_docker("kraken2", inner, vols)

    return {
        "kraken2_report": str(report),
        "kraken2_abundance": str(bracken if bracken.exists() else report),
        "top_genera": [],
        "classification_rate": 0.5,
    }
