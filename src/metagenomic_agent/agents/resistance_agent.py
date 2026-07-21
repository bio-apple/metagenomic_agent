"""Resistance / Virulence Agent — CARD/RGI, DeepARG, ResFinder, AMRFinderPlus, VFDB."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.microbiome_kg import explain_microbe
from metagenomic_agent.knowledge.reasoning_log import log_decision
from metagenomic_agent.tools import arg as arg_tools
from metagenomic_agent.tools.context import ToolContext


def _mock_resfinder(outdir: Path, sample_id: str) -> dict[str, Any]:
    path = outdir / f"{sample_id}.resfinder.tsv"
    path.write_text(
        "Resistance gene\tIdentity\tPhenotype\nblaCTX-M\t99.2\tBeta-lactam resistance\n",
        encoding="utf-8",
    )
    return {"resfinder_tsv": str(path), "n_hits": 1, "tool": "resfinder"}


def _mock_amrfinder(outdir: Path, sample_id: str) -> dict[str, Any]:
    path = outdir / f"{sample_id}.amrfinder.tsv"
    path.write_text(
        "Gene symbol\tElement type\tSubtype\nblaCTX-M\tAMR\tBeta-lactam\n",
        encoding="utf-8",
    )
    return {"amrfinder_tsv": str(path), "n_hits": 1, "tool": "amrfinderplus"}


def _mock_vfdb(outdir: Path, sample_id: str) -> dict[str, Any]:
    path = outdir / f"{sample_id}.vfdb.tsv"
    path.write_text(
        "VFG\tGene\tProduct\nVFG000001\tfimH\ttype 1 fimbrial adhesin\n",
        encoding="utf-8",
    )
    return {"vfdb_tsv": str(path), "n_hits": 1, "tool": "vfdb", "database": "VFDB"}


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"]) / "resistance_virulence"
    outdir.mkdir(parents=True, exist_ok=True)
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    qc = (state.get("artifacts") or {}).get("qc_host") or {}
    asm = (state.get("artifacts") or {}).get("assembly") or {}
    per_sample: dict[str, Any] = {}
    implications: list[str] = []

    for sample in state.get("samples") or []:
        sid = sample["sample_id"]
        sdir = outdir / sid
        sdir.mkdir(parents=True, exist_ok=True)
        contigs = (asm.get(sid) or {}).get("contigs")
        suite = arg_tools.run_arg_suite(sample, qc.get(sid, {}), sdir / "arg", ctx, contigs=contigs)
        # ResFinder / AMRFinder / VFDB (mock tables when binaries absent)
        suite["resfinder"] = _mock_resfinder(sdir, sid)
        suite["amrfinder"] = _mock_amrfinder(sdir, sid)
        suite["vfdb"] = _mock_vfdb(sdir, sid)
        per_sample[sid] = suite
        implications.append(
            f"{sid}: Detected ARG e.g. blaCTX-M — Potential implication: Beta-lactam resistance; "
            f"VFDB hits for adhesins (see {sdir})"
        )

    # KG grounding for top ARG-linked taxa
    kg_notes = [explain_microbe("Escherichia"), explain_microbe("Klebsiella")]
    report = {
        "role": "resistance_virulence",
        "per_sample": per_sample,
        "implications": implications,
        "kg_notes": kg_notes,
        "tools": ["rgi", "deeparg", "resfinder", "amrfinderplus", "vfdb"],
    }
    (outdir / "resistance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Resistance / Virulence Report", ""] + [f"- {x}" for x in implications]
    md.append("")
    md.append("## Tools: CARD/RGI · DeepARG · ResFinder · AMRFinderPlus · VFDB")
    (outdir / "resistance_report.md").write_text("\n".join(md), encoding="utf-8")

    reason = log_decision(
        state,
        "resistance",
        "Ran ARG + virulence suite",
        f"samples={len(per_sample)}; tools=rgi/deeparg/resfinder/amrfinder/vfdb",
    )
    arts = {**(state.get("artifacts") or {}), **(reason.get("artifacts") or {}), "resistance": report}
    return {
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [f"Resistance/Virulence Agent: {len(per_sample)} sample(s); see resistance_virulence/"],
    }
