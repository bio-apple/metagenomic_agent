"""Evidence-chain claims — every biological statement must carry measured stats + DB/literature IDs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.rag.authority import authority_context_block, filter_ungrounded_taxa, ground_taxon


def _biomarker_lookup(stats: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for b in stats.get("biomarker_list") or []:
        g = b.get("genus")
        if g:
            out[g] = b
    return out


def _abundance_for_genus(state: dict[str, Any], genus: str) -> list[dict[str, Any]]:
    rows = []
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    groups = stats.get("groups") or {}
    mat_path = Path(stats.get("genus_matrix") or Path(state["outdir"]) / "diversity_analysis" / "genus_matrix.tsv")
    if mat_path.exists():
        lines = mat_path.read_text(encoding="utf-8").splitlines()
        if lines:
            header = lines[0].split("\t")[1:]
            if genus in header:
                idx = header.index(genus)
                for line in lines[1:]:
                    parts = line.split("\t")
                    sid = parts[0]
                    try:
                        val = float(parts[idx + 1])
                    except (IndexError, ValueError):
                        continue
                    rows.append({"sample": sid, "group": groups.get(sid, "unknown"), "relative_abundance": val})
    if not rows:
        # fallback from taxonomy tops metadata
        for sid, art in (state.get("artifacts") or {}).get("taxonomy", {}).items():
            if genus in (art.get("top_genera") or []):
                rows.append({"sample": sid, "group": "unknown", "relative_abundance": None, "note": "listed_in_top_genera"})
    return rows


def build_claim(
    taxon: str,
    state: dict[str, Any],
    *,
    direction: str = "",
    papers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one grounded claim; reject if taxon not in authority DBs."""
    ground = ground_taxon(taxon)
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    bio = _biomarker_lookup(stats).get(taxon) or {}
    abundances = _abundance_for_genus(state, taxon)
    mean_ab = None
    if abundances:
        vals = [a["relative_abundance"] for a in abundances if a.get("relative_abundance") is not None]
        if vals:
            mean_ab = sum(vals) / len(vals)

    pmid_list = []
    for p in papers or []:
        pmid = p.get("pmid")
        if pmid and str(pmid) not in {"kb", "mock", ""}:
            pmid_list.append(
                {
                    "pmid": str(pmid),
                    "title": p.get("title"),
                    "url": p.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "source": p.get("source"),
                }
            )

    # curated evidence links from bio RAG index
    from metagenomic_agent.rag import evidence_for_taxon

    curated = evidence_for_taxon(taxon)
    for c in curated:
        if c.get("pmid"):
            pmid_list.append(
                {
                    "pmid": str(c["pmid"]),
                    "title": f"{c.get('species')} / {c.get('disease')} ({c.get('effect')})",
                    "url": c.get("url"),
                    "source": c.get("source", "curated"),
                }
            )

    # dedupe pmids
    seen: set[str] = set()
    refs = []
    for p in pmid_list:
        if p["pmid"] in seen:
            continue
        seen.add(p["pmid"])
        refs.append(p)

    interp_cfg = (state.get("config") or {}).get("interpretation") or {}
    require_chain = bool(interp_cfg.get("require_evidence_chain", True))
    # Hallucination guard: differential claims need real table stats (p_value);
    # when require_evidence_chain, abundance-only top_genera are not enough.
    has_table_stats = bio.get("p_value") is not None
    has_abundance = mean_ab is not None or bool(abundances)
    if require_chain:
        allowed = bool(ground["grounded"]) and has_table_stats
    else:
        allowed = bool(ground["grounded"]) and (has_table_stats or has_abundance)
    statement = None
    if allowed:
        bits = [f"**{ground.get('canonical_name') or taxon}**"]
        if direction or bio.get("direction"):
            bits.append(f"方向: `{direction or bio.get('direction')}`")
        if mean_ab is not None:
            bits.append(f"均值相对丰度={mean_ab:.4f}")
        if bio.get("p_value") is not None:
            bits.append(f"p={bio.get('p_value'):.4g}")
        if bio.get("q_value") is not None:
            bits.append(f"FDR q={bio.get('q_value'):.4g}")
        if bio.get("log2fc") is not None:
            bits.append(f"log2FC={bio.get('log2fc'):.3f}")
        db_ids = ", ".join(f"{d['database']}:{d['id']}" for d in (ground.get("database_ids") or [])[:3])
        if db_ids:
            bits.append(f"DB=[{db_ids}]")
        if refs:
            bits.append("PMID=" + ",".join(r["pmid"] for r in refs[:3]))
        statement = "；".join(bits) + "。"
        statement += " 以上陈述仅基于本样本测定值与权威库/文献检索，未经验证的因果关系不作断言。"
    else:
        if ground["grounded"] and require_chain and not has_table_stats:
            statement = (
                f"拒绝无表统计陈述：`{taxon}` 已锚定但不在 biomarkers/LEfSe 表或缺少 p_value "
                f"（抗幻觉：差异/PCoA 解读必须引用程序生成表格）。"
            )
        else:
            statement = (
                f"拒绝无依据陈述：`{taxon}` 未在 GTDB/NCBI 索引中锚定，"
                f"或缺少丰度/显著性统计支撑（抗幻觉策略）。"
            )

    return {
        "taxon": taxon,
        "canonical_name": ground.get("canonical_name"),
        "allowed": allowed,
        "grounded": ground["grounded"],
        "statement": statement,
        "measurements": {
            "mean_relative_abundance": mean_ab,
            "per_sample": abundances,
            "p_value": bio.get("p_value"),
            "q_value": bio.get("q_value"),
            "log2fc": bio.get("log2fc"),
            "direction": direction or bio.get("direction"),
            "effect_size": bio.get("log2fc") if bio.get("log2fc") is not None else bio.get("lda_score"),
            "from_biomarker_table": has_table_stats,
        },
        "database_ids": ground.get("database_ids") or [],
        "references": refs[:8],
        "authority_context": authority_context_block(taxon),
        "policy": "table_bound_stats_and_authority_dbs",
    }


def build_evidence_chains(state: dict[str, Any]) -> dict[str, Any]:
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    genera = [b["genus"] for b in stats.get("biomarker_list") or [] if b.get("genus")]
    if not genera:
        for art in (state.get("artifacts") or {}).get("taxonomy", {}).values():
            genera.extend(art.get("top_genera") or [])
        genera = list(dict.fromkeys(genera))[:8]

    grounded, rejected = filter_ungrounded_taxa(genera)
    lit = state.get("literature") or (state.get("artifacts") or {}).get("literature") or {}
    papers_by_genus: dict[str, list] = {}
    for entry in lit.get("entries") or []:
        papers_by_genus[entry.get("genus")] = entry.get("papers") or []

    claims = []
    for g in grounded:
        taxon = g["taxon"]
        bio = _biomarker_lookup(stats).get(taxon) or {}
        claims.append(
            build_claim(
                taxon,
                state,
                direction=str(bio.get("direction") or ""),
                papers=papers_by_genus.get(taxon),
            )
        )

    report = {
        "n_candidates": len(genera),
        "n_grounded": len(grounded),
        "n_rejected_ungrounded": len(rejected),
        "rejected_taxa": rejected,
        "claims": claims,
        "policy": (
            "Agents may only assert biology for taxa grounded in GTDB/NCBI curated authority index "
            "and must attach abundance and/or p-value plus database IDs / PMIDs when available."
        ),
    }
    return report


def write_evidence_chains(state: dict[str, Any]) -> dict[str, Any]:
    report = build_evidence_chains(state)
    out = Path(state["outdir"]) / "evidence"
    out.mkdir(parents=True, exist_ok=True)
    (out / "claims.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Evidence-grounded claims（抗幻觉）",
        "",
        report["policy"],
        "",
        f"- candidates: {report['n_candidates']}",
        f"- grounded: {report['n_grounded']}",
        f"- rejected (ungrounded): {report['n_rejected_ungrounded']}",
        "",
    ]
    if report["rejected_taxa"]:
        lines.append("## Rejected taxa（未在权威库锚定）")
        for t in report["rejected_taxa"]:
            lines.append(f"- `{t}`")
        lines.append("")
    lines.append("## Claims")
    lines.append("")
    for c in report["claims"]:
        status = "ALLOWED" if c["allowed"] else "BLOCKED"
        lines.append(f"### {c.get('canonical_name') or c['taxon']} [{status}]")
        lines.append(c.get("statement") or "")
        m = c.get("measurements") or {}
        lines.append(
            f"- abundance(mean)={m.get('mean_relative_abundance')}；"
            f"p={m.get('p_value')}；q={m.get('q_value')}；log2FC={m.get('log2fc')}"
        )
        for d in c.get("database_ids") or []:
            lines.append(f"- DB: {d.get('database')}:{d.get('id')} ({d.get('name')})")
        for r in c.get("references") or []:
            lines.append(f"- PMID {r.get('pmid')}: {r.get('title')} {r.get('url') or ''}")
        lines.append("")
    (out / "claims.md").write_text("\n".join(lines), encoding="utf-8")
    report["path"] = str(out / "claims.md")
    return report
