"""MAG Discovery Agent — thin orchestration facade over assembly/binning/refinement.

Roadmap alias: MAG Agent delegates to Assembly Agent with DAS Tool + CheckM2 + BUSCO.
"""

from __future__ import annotations

from typing import Any

from metagenomic_agent.agents import assembly_agent


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ensure MAG-oriented defaults then run the assembly/binning pipeline."""
    cfg = dict(state.get("config") or {})
    pipe = dict(cfg.get("pipeline") or {})
    pipe["enable_assembly"] = True
    pipe.setdefault("binners", ["metabat2", "maxbin2", "concoct", "vamb"])
    cfg["pipeline"] = pipe
    node = dict(node or {})
    params = dict(node.get("params") or {})
    params.setdefault("binners", pipe["binners"])
    bio = dict((state.get("artifacts") or {}).get("bio_reasoning") or {})
    if bio.get("assembler_preference"):
        params.setdefault("assembler", bio["assembler_preference"])
    node["params"] = params
    out = assembly_agent.run({**state, "config": cfg}, node)
    arts = dict(state.get("artifacts") or {})
    arts["mag"] = {
        "summary": out.get("mag_summary"),
        "stats": out.get("mag_summary_stats"),
        "agent": "mag_discovery",
    }
    return {**out, "artifacts": {**arts, **(out.get("artifacts") or {})}, "config": cfg}
