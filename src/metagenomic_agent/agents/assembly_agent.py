"""Assembly Agent — MEGAHIT (+ binning hooks)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import megahit
from metagenomic_agent.tools.context import ToolContext


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    per_sample: dict[str, Any] = {}
    for sample in state["samples"]:
        sid = sample["sample_id"]
        per_sample[sid] = megahit.run(sample, qc_arts.get(sid, {}), outdir / sid / "assembly", ctx=ctx)
    return {"assembly": per_sample}
