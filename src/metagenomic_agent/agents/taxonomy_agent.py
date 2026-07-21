"""Taxonomy Agent — Kraken2/Bracken + MetaPhlAn."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import kraken, metaphlan
from metagenomic_agent.tools.context import ToolContext


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    tools = (node or {}).get("params", {}).get("tools") or (node or {}).get("tools") or ["kraken2", "metaphlan"]
    confidence = float((node or {}).get("params", {}).get("confidence", 0.05))
    qc_arts = state.get("artifacts", {}).get("qc_host", {})

    per_sample: dict[str, Any] = {}
    merged_rows = ["sample\tgenus\trelative_abundance\ttool"]

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        tax_dir = outdir / sid / "taxonomy"
        art: dict[str, Any] = {"top_genera": [], "classification_rate": 0.0}
        if "kraken2" in tools or "bracken" in tools:
            k = kraken.run(
                sample,
                upstream,
                tax_dir,
                ctx=ctx,
                confidence=confidence,
                read_length=sample.get("read_length_est", 150),
            )
            art.update(k)
            art["top_genera"] = list(dict.fromkeys(art.get("top_genera", []) + k.get("top_genera", [])))
            _append_abundance(merged_rows, sid, k.get("kraken2_abundance"), "kraken2")
        if "metaphlan" in tools or "metaphlan4" in tools:
            m = metaphlan.run(sample, upstream, tax_dir, ctx=ctx)
            art.update(m)
            art["top_genera"] = list(dict.fromkeys(art.get("top_genera", []) + m.get("top_genera", [])))
            _append_abundance(merged_rows, sid, m.get("metaphlan_abundance"), "metaphlan")
        per_sample[sid] = art

    profile = outdir / "taxonomy_profile.tsv"
    profile.write_text("\n".join(merged_rows) + "\n", encoding="utf-8")
    return {"taxonomy": per_sample, "taxonomy_profile": str(profile)}


def _append_abundance(rows: list[str], sample_id: str, path: str | None, tool: str) -> None:
    if not path or not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines()[1:]:
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            rows.append(f"{sample_id}\t{parts[0]}\t{parts[1]}\t{tool}")
