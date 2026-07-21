"""Resistance / Virulence Agent — CARD/RGI, DeepARG, ResFinder, AMRFinderPlus, VFDB.

Informed by Feldgarden et al. 2021 (AMRFinderPlus / Reference Gene Catalog).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.microbiome_kg import explain_microbe
from metagenomic_agent.knowledge.reasoning_log import log_decision
from metagenomic_agent.tools import arg as arg_tools
from metagenomic_agent.tools.context import ToolContext


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
        # Without contigs, still allow read-based DeepARG; AMRFinder needs nucleotide/protein
        if not contigs:
            # Use QC clean reads path placeholder for mock contig-less runs
            contigs = (qc.get(sid) or {}).get("nonhost_r1") or sample.get("r1")
        suite = arg_tools.run_arg_suite(sample, qc.get(sid, {}), sdir / "arg", ctx, contigs=contigs)
        # Ensure catalog tools always present (suite embeds them when contigs set)
        if "amrfinder" not in suite and contigs:
            suite["amrfinder"] = arg_tools.run_amrfinderplus(str(contigs), sdir / "amrfinder", ctx, sid)
        if "resfinder" not in suite and contigs:
            suite["resfinder"] = arg_tools.run_resfinder(str(contigs), sdir / "resfinder", ctx, sid)
        if "vfdb" not in suite and contigs:
            suite["vfdb"] = arg_tools.run_vfdb_blast(str(contigs), sdir / "vfdb", ctx, sid)
        per_sample[sid] = suite
        amr_n = (suite.get("amrfinder") or {}).get("n_hits") or suite.get("n_hits") or 0
        vf_n = (suite.get("vfdb") or {}).get("n_hits") or 0
        implications.append(
            f"{sid}: AMR/virulence hits amrfinder={amr_n} vfdb={vf_n} "
            f"(Reference Gene Catalog–style reporting; see {sdir})"
        )

    kg_notes = [explain_microbe("Escherichia"), explain_microbe("Klebsiella")]
    report = {
        "role": "resistance_virulence",
        "per_sample": per_sample,
        "implications": implications,
        "kg_notes": kg_notes,
        "tools": ["rgi", "deeparg", "resfinder", "amrfinderplus", "vfdb"],
        "literature": "Feldgarden et al. 2021 Sci Rep — AMRFinderPlus / Reference Gene Catalog",
    }
    (outdir / "resistance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Resistance / Virulence Report", ""] + [f"- {x}" for x in implications]
    md.append("")
    md.append("## Tools: CARD/RGI · DeepARG · ResFinder · AMRFinderPlus · VFDB")
    md.append("")
    md.append(f"_Literature: {report['literature']}_")
    (outdir / "resistance_report.md").write_text("\n".join(md), encoding="utf-8")

    reason = log_decision(
        state,
        "resistance",
        "Ran ARG + virulence suite (AMRFinderPlus catalog)",
        f"samples={len(per_sample)}; tools=rgi/deeparg/resfinder/amrfinder/vfdb",
    )
    arts = {**(state.get("artifacts") or {}), **(reason.get("artifacts") or {}), "resistance": report}
    return {
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [f"Resistance/Virulence Agent: {len(per_sample)} sample(s); see resistance_virulence/"],
    }
