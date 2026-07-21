"""Function Agent — pathway / gene annotation profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import functional
from metagenomic_agent.tools.context import ToolContext


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    per_sample: dict[str, Any] = {}
    merged = ["sample\tfeature\tabundance\tdatabase"]

    for sample in state["samples"]:
        sid = sample["sample_id"]
        art = functional.run(sample, qc_arts.get(sid, {}), outdir / sid / "functional", ctx=ctx)
        per_sample[sid] = art
        path = art.get("functional_profile")
        if path and Path(path).exists():
            for line in Path(path).read_text().splitlines()[1:]:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    merged.append(f"{sid}\t{parts[0]}\t{parts[1]}\t{parts[2]}")

    profile = outdir / "functional_profile.tsv"
    profile.write_text("\n".join(merged) + "\n", encoding="utf-8")
    return {"functional": per_sample, "functional_profile": str(profile)}
