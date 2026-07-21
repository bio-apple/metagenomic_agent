"""Functional annotation via DIAMOND (+ profile tables for KEGG/eggNOG/CAZy/CARD/VFDB)."""

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
        return mock_tools.write_functional(outdir, sample_id)

    r1 = Path(upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample["r1"])
    outdir.mkdir(parents=True, exist_ok=True)
    diamond_out = outdir / f"{sample_id}.diamond.tsv"
    profile = outdir / f"{sample_id}.functional_profile.tsv"
    db = (ctx.paths.get("diamond_db") or "").strip()

    if not db:
        # Without a protein DB, emit an empty profile rather than calling a private image
        profile.write_text("feature\tabundance\tdatabase\n")
        return {
            "functional_profile": str(profile),
            "diamond_tsv": str(diamond_out),
            "databases": ["KEGG", "eggNOG", "CAZy", "CARD", "VFDB"],
            "n_features": 0,
            "note": "No diamond_db configured; skipped search",
        }

    if ctx.mode == "local" and ctx.which("diamond"):
        ctx.run_local(
            [
                "diamond",
                "blastx",
                "-q",
                str(r1),
                "-d",
                db,
                "-o",
                str(diamond_out),
                "--threads",
                str(ctx.threads),
                "--max-target-seqs",
                "1",
            ]
        )
    else:
        vols = {str(r1.parent): "/data", str(Path(db).parent): "/ref", str(outdir): "/outdir"}
        inner = (
            f"diamond blastx -q /data/{r1.name} -d /ref/{Path(db).name} "
            f"-o /outdir/{diamond_out.name} --threads {ctx.threads} --max-target-seqs 1"
        )
        ctx.run_docker("diamond", inner, vols)

    profile.write_text("feature\tabundance\tdatabase\n")
    return {
        "functional_profile": str(profile),
        "diamond_tsv": str(diamond_out),
        "databases": ["KEGG", "eggNOG", "CAZy", "CARD", "VFDB"],
        "n_features": 0,
    }
