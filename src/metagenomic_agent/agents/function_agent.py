"""Function Agent — pathway / gene annotation + biological mechanism notes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.rag import retrieve
from metagenomic_agent.tools import functional
from metagenomic_agent.tools.context import ToolContext

MECHANISM_HINTS = {
    "butyrate": (
        "Butyrate-related pathways can affect gut barrier and anti-inflammatory signaling; "
        "interpret alongside taxa (e.g. Faecalibacterium)."
    ),
    "butanoate": (
        "Changes in butanoate metabolism modules suggest altered SCFA production potential; "
        "do not equate directly with clinical efficacy."
    ),
    "starch": "Shifts in polysaccharide degradation capacity often relate to dietary fiber exposure.",
    "beta-lactam": (
        "Beta-lactamase–related functions suggest AMR potential; align with CARD evidence."
    ),
    "nitrate": "Nitrate reduction can occur in facultative anaerobe enrichment contexts.",
}


def _interpret_functions(profile_path: Path, disease: str | None) -> dict[str, Any]:
    features: list[str] = []
    if profile_path.exists():
        for line in profile_path.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if parts:
                features.append(parts[1] if len(parts) > 1 else parts[0])
    features = list(dict.fromkeys(features))[:20]
    notes = []
    lines = ["# Functional biological interpretation", ""]
    if disease:
        lines.append(f"Disease/phenotype context: `{disease}`.")
        lines.append("")
    for feat in features[:12]:
        kegg = retrieve("kegg", feat, top_k=1)
        card = retrieve("card", feat, top_k=1)
        uniprot = retrieve("uniprot", feat, top_k=1)
        mech = None
        blob = feat.lower()
        for key, text in MECHANISM_HINTS.items():
            if key in blob:
                mech = text
                break
        if not mech and kegg:
            mech = f"KEGG hit `{kegg[0].get('id')}` ({kegg[0].get('name')}) — {kegg[0].get('pathway') or ''}."
        entry = {
            "feature": feat,
            "kegg": kegg[:1],
            "card": card[:1],
            "uniprot": uniprot[:1],
            "mechanism_note": mech or "No curated mechanism note; report abundance only.",
        }
        notes.append(entry)
        lines.append(f"## {feat}")
        lines.append(f"- {entry['mechanism_note']}")
        if kegg:
            lines.append(f"- KEGG: {kegg[0].get('id')} {kegg[0].get('name')}")
        if card:
            lines.append(f"- CARD: {card[0].get('id')} {card[0].get('name')}")
        lines.append("")
    lines.append(
        "Functional changes do not prove mechanism; causal inference requires experimental validation."
    )
    return {"notes": notes, "markdown": "\n".join(lines)}


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    per_sample: dict[str, Any] = {}
    merged = ["sample\tfeature\tabundance\tdatabase"]

    pipe = (state.get("config") or {}).get("pipeline") or {}
    enable_arg = bool(pipe.get("enable_arg", False))
    asm_arts = (state.get("artifacts") or {}).get("assembly") or {}

    for sample in state["samples"]:
        sid = sample["sample_id"]
        art = functional.run(sample, qc_arts.get(sid, {}), outdir / sid / "functional", ctx=ctx)
        if enable_arg:
            from metagenomic_agent.tools import arg as arg_tools

            contigs = (asm_arts.get(sid) or {}).get("contigs")
            art["arg"] = arg_tools.run_arg_suite(
                sample, qc_arts.get(sid, {}), outdir / sid / "arg", ctx, contigs=contigs
            )
        per_sample[sid] = art
        path = art.get("functional_profile")
        if path and Path(path).exists():
            for line in Path(path).read_text().splitlines()[1:]:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    merged.append(f"{sid}\t{parts[0]}\t{parts[1]}\t{parts[2]}")

    profile = outdir / "functional_profile.tsv"
    profile.write_text("\n".join(merged) + "\n", encoding="utf-8")

    disease = ((node or {}).get("params") or {}).get("disease_context") or (
        (state.get("artifacts") or {}).get("bio_reasoning") or {}
    ).get("disease_context")
    interpretation = _interpret_functions(profile, disease)
    interp_path = outdir / "functional_interpretation.md"
    interp_path.write_text(interpretation["markdown"], encoding="utf-8")
    (outdir / "functional_interpretation.json").write_text(
        json.dumps(interpretation["notes"], indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "functional": per_sample,
        "functional_profile": str(profile),
        "functional_interpretation": interpretation,
        "functional_interpretation_path": str(interp_path),
    }
