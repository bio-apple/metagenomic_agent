"""Hallucination guardrails — interpretations may only cite program-generated table rows.

Species names, p-values, q-values, effect sizes (log2FC / LDA) for differential /
pathway / PCoA narratives must come from statistics / diversity / function tables.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


def _load_biomarker_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    rows = list(stats.get("biomarker_list") or [])
    if rows:
        return rows
    # Fallback: read biomarkers.tsv
    outdir = Path(state.get("outdir") or ".")
    for rel in ("biomarkers/biomarkers.tsv", "biomarkers/lefse_like.tsv"):
        path = outdir / rel
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for r in reader:
                genus = r.get("genus") or r.get("feature") or r.get("taxon")
                if not genus:
                    continue
                row = {"genus": genus, "source_table": rel}
                for key, dest in (
                    ("p_value", "p_value"),
                    ("q_value", "q_value"),
                    ("log2fc", "log2fc"),
                    ("lda_score", "lda_score"),
                    ("direction", "direction"),
                    ("group", "group"),
                ):
                    if r.get(key) not in (None, ""):
                        try:
                            row[dest] = float(r[key]) if key != "direction" and key != "group" else r[key]
                        except ValueError:
                            row[dest] = r[key]
                rows.append(row)
        if rows:
            break
    return rows


def _load_pathway_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    arts = state.get("artifacts") or {}
    rows: list[dict[str, Any]] = []
    func = arts.get("functional") or arts.get("function") or {}
    if isinstance(func, dict):
        for sid, v in func.items():
            if not isinstance(v, dict):
                continue
            for key in ("top_pathways", "pathways", "kegg", "cog", "go"):
                val = v.get(key)
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            rows.append({**item, "sample_id": sid, "ontology": key, "source_table": "functional"})
                        else:
                            rows.append({"pathway": str(item), "sample_id": sid, "ontology": key, "source_table": "functional"})
                elif isinstance(val, dict):
                    for name, score in list(val.items())[:50]:
                        rows.append(
                            {
                                "pathway": str(name),
                                "score": score,
                                "sample_id": sid,
                                "ontology": key,
                                "source_table": "functional",
                            }
                        )
    # Optional pathway TSV
    path = Path(state.get("outdir") or ".") / "functional_profile.tsv"
    if path.exists() and not rows:
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for r in reader:
                rows.append({**r, "source_table": "functional_profile.tsv"})
    return rows


def _pcoa_summary(state: dict[str, Any]) -> dict[str, Any] | None:
    outdir = Path(state.get("outdir") or ".")
    for rel in (
        "report/figures/pcoa.json",
        "diversity_analysis/beta_diversity.json",
        "diversity_analysis/pcoa.json",
    ):
        p = outdir / rel
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return {"path": str(p), "keys": list(data.keys())[:12] if isinstance(data, dict) else [], "source_table": rel}
            except json.JSONDecodeError:
                return {"path": str(p), "source_table": rel}
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    if stats.get("beta") or stats.get("pcoa"):
        return {"source_table": "statistics", "beta": bool(stats.get("beta")), "pcoa": bool(stats.get("pcoa"))}
    return None


def table_bound_universe(state: dict[str, Any]) -> dict[str, Any]:
    """Allowed entities/stats extractable only from program tables."""
    biomarkers = _load_biomarker_rows(state)
    pathways = _load_pathway_rows(state)
    taxa = sorted({str(b.get("genus")) for b in biomarkers if b.get("genus")})
    stats_index: dict[str, dict[str, Any]] = {}
    for b in biomarkers:
        g = str(b.get("genus"))
        stats_index[g] = {
            "p_value": b.get("p_value"),
            "q_value": b.get("q_value"),
            "log2fc": b.get("log2fc"),
            "lda_score": b.get("lda_score"),
            "direction": b.get("direction"),
            "source_table": b.get("source_table") or "biomarker_list",
        }
    pathway_names = sorted(
        {
            str(p.get("pathway") or p.get("name") or p.get("id"))
            for p in pathways
            if p.get("pathway") or p.get("name") or p.get("id")
        }
    )
    return {
        "allowed_taxa": taxa,
        "stats_by_taxon": stats_index,
        "allowed_pathways": pathway_names,
        "pathway_rows": pathways[:80],
        "pcoa": _pcoa_summary(state),
        "n_biomarkers": len(biomarkers),
        "policy": "cite_only_program_generated_tables",
    }


def assert_stats_from_table(
    taxon: str,
    *,
    p_value: Any = None,
    q_value: Any = None,
    effect_size: Any = None,
    universe: dict[str, Any],
) -> dict[str, Any]:
    """Verify cited stats match the table row for taxon (tolerance for float fmt)."""
    row = (universe.get("stats_by_taxon") or {}).get(taxon)
    if not row:
        return {
            "ok": False,
            "reason": f"taxon `{taxon}` not in biomarkers/LEfSe tables",
            "taxon": taxon,
        }
    issues = []
    if p_value is not None and row.get("p_value") is not None:
        try:
            if abs(float(p_value) - float(row["p_value"])) > 1e-9:
                issues.append(f"p_value mismatch table={row['p_value']} cited={p_value}")
        except (TypeError, ValueError):
            issues.append("p_value not numeric")
    elif p_value is not None and row.get("p_value") is None:
        issues.append("p_value cited but missing in table")
    if q_value is not None and row.get("q_value") is not None:
        try:
            if abs(float(q_value) - float(row["q_value"])) > 1e-9:
                issues.append(f"q_value mismatch table={row['q_value']} cited={q_value}")
        except (TypeError, ValueError):
            issues.append("q_value not numeric")
    if effect_size is not None:
        table_eff = row.get("log2fc") if row.get("log2fc") is not None else row.get("lda_score")
        if table_eff is None:
            issues.append("effect size cited but missing in table")
        else:
            try:
                if abs(float(effect_size) - float(table_eff)) > 1e-6:
                    issues.append(f"effect mismatch table={table_eff} cited={effect_size}")
            except (TypeError, ValueError):
                issues.append("effect size not numeric")
    return {"ok": len(issues) == 0, "issues": issues, "taxon": taxon, "table_row": row}


def sanitize_interpretation_text(text: str, universe: dict[str, Any]) -> dict[str, Any]:
    """Flag Latin binomial / genus-like tokens not present in allowed tables."""
    allowed = set(universe.get("allowed_taxa") or [])
    allowed_l = {a.lower() for a in allowed}
    # Simple genus-like tokens (Capitalized word 5+ letters)
    candidates = set(re.findall(r"\b([A-Z][a-z]{4,})\b", text or ""))
    # Filter common English words
    stop = {
        "Overall", "However", "Therefore", "Figure", "Table", "Group", "Control",
        "Shannon", "Simpson", "Bray", "Curtis", "PCoA", "NMDS", "LEfSe", "KEGG",
        "Relative", "Abundance", "Significant", "Analysis", "Results", "Sample",
    }
    suspects = sorted(c for c in candidates if c not in stop and c.lower() not in allowed_l)
    # Also catch Fake-style from citations of known blocked
    return {
        "text": text,
        "allowed_taxa_mentioned": sorted(c for c in candidates if c.lower() in allowed_l),
        "ungrounded_name_suspects": suspects,
        "ok": len(suspects) == 0,
        "policy": "strip_or_block_ungrounded_taxon_names",
    }


def grounded_interpretation_bundle(state: dict[str, Any]) -> dict[str, Any]:
    """Bundle for Reporter / Interpreter / Literature — table-bound claims only."""
    cfg = (state.get("config") or {}).get("interpretation") or {}
    require_chain = bool(cfg.get("require_evidence_chain", True))
    require_grounding = bool(cfg.get("require_grounding", True))
    universe = table_bound_universe(state)

    from metagenomic_agent.knowledge.evidence_chain import build_evidence_chains
    from metagenomic_agent.rag.authority import ground_taxon

    chains = build_evidence_chains(state)
    allowed_claims = []
    blocked_claims = []
    for c in chains.get("claims") or []:
        taxon = c.get("taxon")
        in_table = taxon in (universe.get("stats_by_taxon") or {})
        meas = c.get("measurements") or {}
        has_stats = meas.get("p_value") is not None
        # Differential / LEfSe narrative: must bind to table stats when policy on
        if require_chain and not has_stats:
            c = {
                **c,
                "allowed": False,
                "statement": (
                    f"Rejected table-free statistical claim: `{taxon}` is not in biomarkers/LEfSe "
                    f"tables or lacks p_value "
                    f"(anti-hallucination: PCoA/differential interpretation must cite program tables)."
                ),
                "block_reason": "missing_table_stats",
            }
        if require_grounding and not c.get("grounded"):
            c = {**c, "allowed": False, "block_reason": c.get("block_reason") or "ungrounded"}
        if require_chain and has_stats and not in_table:
            # stats invented not from table
            c = {**c, "allowed": False, "block_reason": "stats_not_in_table"}
        if c.get("allowed"):
            # Force statement numbers from table row
            row = (universe.get("stats_by_taxon") or {}).get(taxon) or {}
            g = ground_taxon(taxon)
            name = g.get("canonical_name") or taxon
            bits = [f"**{name}**"]
            if row.get("direction"):
                bits.append(f"direction=`{row['direction']}`")
            if row.get("p_value") is not None:
                bits.append(f"p={float(row['p_value']):.4g}")
            if row.get("q_value") is not None:
                bits.append(f"q={float(row['q_value']):.4g}")
            if row.get("log2fc") is not None:
                bits.append(f"log2FC={float(row['log2fc']):.3f}")
            elif row.get("lda_score") is not None:
                bits.append(f"LDA={float(row['lda_score']):.3f}")
            bits.append(f"source_table=`{row.get('source_table', 'biomarker_list')}`")
            c = {**c, "statement": "; ".join(bits) + ".", "table_bound": True}
            allowed_claims.append(c)
        else:
            blocked_claims.append(c)

    bullets = [c.get("statement") for c in allowed_claims if c.get("statement")]
    pcoa = universe.get("pcoa")
    pcoa_note = (
        f"PCoA/Beta plot data from `{pcoa.get('source_table')}`; "
        f"do not introduce taxa outside the table in interpretation."
        if pcoa
        else "No PCoA JSON found; avoid quantitative claims about uncomputed beta diversity."
    )
    pathway_bullets = [
        f"- Pathway `{p}` (from functional table)" for p in (universe.get("allowed_pathways") or [])[:8]
    ]

    return {
        "policy": "table_bound_no_hallucinated_taxa_pvalues_effects",
        "require_evidence_chain": require_chain,
        "require_grounding": require_grounding,
        "universe": {
            "allowed_taxa": universe["allowed_taxa"],
            "allowed_pathways": universe["allowed_pathways"],
            "n_biomarkers": universe["n_biomarkers"],
            "pcoa": pcoa,
        },
        "allowed_claims": allowed_claims,
        "blocked_claims": blocked_claims,
        "interpretation_bullets": bullets,
        "pcoa_note": pcoa_note,
        "pathway_bullets": pathway_bullets,
        "n_allowed": len(allowed_claims),
        "n_blocked": len(blocked_claims),
    }


def write_grounded_interp(state: dict[str, Any]) -> dict[str, Any]:
    bundle = grounded_interpretation_bundle(state)
    out = Path(state["outdir"]) / "evidence"
    out.mkdir(parents=True, exist_ok=True)
    (out / "grounded_interp.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    lines = [
        "# Table-bound biological interpretation",
        "",
        f"- Allowed claims: {bundle['n_allowed']}",
        f"- Blocked: {bundle['n_blocked']}",
        f"- Policy: `{bundle['policy']}`",
        "",
        "## Differential taxa (from program tables only)",
        "",
    ]
    for b in bundle.get("interpretation_bullets") or []:
        lines.append(f"- {b}")
    if not bundle.get("interpretation_bullets"):
        lines.append("- _(no table-bound differential claims)_")
    lines += ["", "## PCoA / Beta", "", f"- {bundle.get('pcoa_note')}", "", "## Pathways", ""]
    lines.extend(bundle.get("pathway_bullets") or ["- _(no pathway rows)_"])
    (out / "grounded_interp.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    bundle["path"] = str(out / "grounded_interp.json")
    return bundle
