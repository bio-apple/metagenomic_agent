"""Manuscript draft generator (template-level, not journal submission-ready prose)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent import __version__

TEMPLATES = ("Nature", "Cell", "ISME Journal", "Microbiome", "Gut Microbes")


def _disease_from_query(q: str) -> str:
    ql = q.lower()
    if "ibd" in ql or "crohn" in ql or "colitis" in ql:
        return "inflammatory bowel disease (IBD)"
    if "tumor" in ql or "cancer" in ql:
        return "tumor-associated microbiome"
    return "the gut microbiome"


def write_manuscript(state: dict[str, Any], template: str = "Microbiome") -> dict[str, str]:
    out = Path(state["outdir"]) / "report" / "manuscript"
    out.mkdir(parents=True, exist_ok=True)
    tpl = template if template in TEMPLATES else "Microbiome"
    query = state.get("user_query") or "metagenomic analysis"
    disease = _disease_from_query(query)
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    biomarkers = stats.get("biomarker_list") or []
    lit = state.get("literature") or {}
    evidence = (state.get("artifacts") or {}).get("evidence_table") or []
    quality = (state.get("artifacts") or {}).get("quality_scores") or {}
    bio_warns = (state.get("validation") or {}).get("biological", {}).get("warnings") or []

    bio_lines = "\n".join(
        f"- {b.get('genus')}: {b.get('direction')} "
        f"(p={b.get('p_value')}, q={b.get('q_value')}, log2FC={b.get('log2fc')})"
        for b in biomarkers[:12]
    ) or "- (no biomarkers detected)"

    ev_lines = "\n".join(
        f"- {e.get('species')}: {e.get('effect')} in {e.get('disease')} (PMID {e.get('pmid')}, source={e.get('source')})"
        for e in evidence[:12]
    ) or "- (see literature_summary/)"

    qs = quality.get("scores") or {}
    q_line = ", ".join(f"{k}={v}" for k, v in qs.items()) if qs else "n/a"

    intro = f"""# Introduction

Gut microbial communities are increasingly linked to {disease}. This automated analysis was driven by the research question:

> {query}

We combined taxonomic profiling, optional functional annotation, differential abundance testing, biological-database RAG, and literature evidence aggregation using metagenomic-agent v{__version__}.
"""

    methods = f"""# Methods

See also `report/methods.md` for the executed DAG and software versions.

Briefly, reads were quality-filtered (fastp), host-filtered when configured, and profiled with Kraken2/MetaPhlAn and/or genomic language-model adapters. Differential abundance used Mann–Whitney U tests with Benjamini–Hochberg FDR. Evidence was retrieved from curated bio-database indices (GTDB/KEGG/CARD/VFDB/MGnify stubs) and literature sources (PubMed/Europe PMC when online). Target journal template: **{tpl}**.
"""

    results = f"""# Results

## Data quality

Quality scores: {q_line}

## Differential taxa

{bio_lines}

## Evidence table highlights

{ev_lines}
"""

    discussion = f"""# Discussion

Observed taxonomic shifts should be interpreted in light of study design, sequencing depth, and database completeness. Literature PMIDs listed in the Evidence Table provide an initial evidence chain and are not a substitute for systematic review.

Biological validator notes:
{chr(10).join('- ' + w for w in bio_warns) or '- none'}
"""

    limitations = """# Limitations

- Default statistics are MWU + BH-FDR, not ANCOM-BC/MaAsLin2/LEfSe.
- Curated bio-RAG indices are compact stubs until full local GTDB/CARD/KEGG dumps are mounted.
- Mock mode synthesizes abundances for software demonstration.
- Manuscript text is template-generated and requires expert editing before submission.
"""

    refs = ["# References", ""]
    for e in evidence[:20]:
        if e.get("pmid") and e.get("pmid") not in {"kb", "mock"}:
            refs.append(f"- PMID {e['pmid']}: {e.get('species')} / {e.get('disease')} ({e.get('effect')})")
    for entry in (lit.get("entries") or [])[:10]:
        for p in entry.get("papers") or []:
            if p.get("pmid") and p.get("pmid") not in {"kb", "mock"}:
                refs.append(f"- {p.get('title')} (PMID {p.get('pmid')})")
    if len(refs) == 2:
        refs.append("- (no external PMIDs in this run; see curated KB)")

    paths = {
        "introduction": str(out / "introduction.md"),
        "methods": str(out / "methods.md"),
        "results": str(out / "results.md"),
        "discussion": str(out / "discussion.md"),
        "limitations": str(out / "limitations.md"),
        "references": str(out / "references.md"),
        "combined": str(out / "manuscript_draft.md"),
    }
    (out / "introduction.md").write_text(intro, encoding="utf-8")
    (out / "methods.md").write_text(methods, encoding="utf-8")
    (out / "results.md").write_text(results, encoding="utf-8")
    (out / "discussion.md").write_text(discussion, encoding="utf-8")
    (out / "limitations.md").write_text(limitations, encoding="utf-8")
    (out / "references.md").write_text("\n".join(refs) + "\n", encoding="utf-8")
    combined = "\n\n".join(
        [
            intro,
            methods,
            results,
            discussion,
            limitations,
            "\n".join(refs),
        ]
    )
    (out / "manuscript_draft.md").write_text(combined, encoding="utf-8")
    (out / "template.txt").write_text(tpl + "\n", encoding="utf-8")
    return paths
