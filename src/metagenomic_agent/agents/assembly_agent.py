"""Assembly Agent — MEGAHIT → MetaBAT2 → GTDB-Tk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import megahit


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    mode = state["mode"]
    cfg = state["config"]
    image = cfg.get("docker", {}).get("image", "meta:latest")
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    per_sample: dict[str, Any] = {}

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        asm_dir = outdir / sid / "assembly"
        per_sample[sid] = megahit.run(sample, upstream, asm_dir, mode=mode, docker_image=image)

    return {"assembly": per_sample}
