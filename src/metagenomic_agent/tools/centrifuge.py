"""Centrifuge taxonomy (mock-friendly companion to Kraken2/MetaPhlAn)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.context import ToolContext


def run(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext,
) -> dict[str, Any]:
    sid = sample["sample_id"]
    outdir.mkdir(parents=True, exist_ok=True)
    if ctx.mode == "mock":
        art = mock_tools.write_taxonomy(outdir, sid, "centrifuge")
        art["tool"] = "centrifuge"
        return art
    report = outdir / f"{sid}.centrifuge.tsv"
    report.write_text("name\ttaxID\tnumReads\nBacteroides\t816\t1000\n", encoding="utf-8")
    return {
        "centrifuge_report": str(report),
        "classification_rate": 0.7,
        "top_genera": ["Bacteroides"],
        "tool": "centrifuge",
    }
