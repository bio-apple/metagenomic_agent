"""Function Agent — KEGG / eggNOG / CAZy / CARD / VFDB."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import functional


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    mode = state["mode"]
    cfg = state["config"]
    image = cfg.get("docker", {}).get("image", "meta:latest")
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    per_sample: dict[str, Any] = {}
    merged = ["sample\tfeature\tabundance\tdatabase"]

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        fun_dir = outdir / sid / "functional"
        art = functional.run(sample, upstream, fun_dir, mode=mode, docker_image=image)
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
