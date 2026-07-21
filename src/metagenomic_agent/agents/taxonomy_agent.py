"""Taxonomy Agent — classic tools + gLM with intelligent routing and fusion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.skills.bandit import EpsilonGreedyBandit
from metagenomic_agent.skills.checker import check_skill_post
from metagenomic_agent.skills.router import route_taxonomy_tools
from metagenomic_agent.tools import glm, kraken, metaphlan
from metagenomic_agent.tools.context import ToolContext


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    requested = (node or {}).get("params", {}).get("tools") or (node or {}).get("tools")
    routing = route_taxonomy_tools(
        state.get("samples") or [],
        state.get("config") or {},
        requested=list(requested) if requested else None,
        outdir=outdir,
    )
    tools = routing["tools"]
    confidence = float((node or {}).get("params", {}).get("confidence", 0.05))
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    bandit = EpsilonGreedyBandit.load(Path(routing["bandit_path"]), epsilon=float((state.get("config") or {}).get("routing", {}).get("epsilon", 0.15)))

    per_sample: dict[str, Any] = {}
    merged_rows = ["sample\tgenus\trelative_abundance\ttool"]
    post_violations: list[dict[str, Any]] = []

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        tax_dir = outdir / sid / "taxonomy"
        tool_results: list[dict[str, Any]] = []
        art: dict[str, Any] = {"top_genera": [], "classification_rate": 0.0, "routing": routing}

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
            tool_results.append(k)
            _append_abundance(merged_rows, sid, k.get("kraken2_abundance"), "kraken2")
            post_violations.extend(check_skill_post("kraken2", k))
            bandit.update("kraken2", success=True, quality=float(k.get("classification_rate") or 0.5), match=0.7)

        if "metaphlan" in tools or "metaphlan4" in tools:
            m = metaphlan.run(sample, upstream, tax_dir, ctx=ctx)
            art.update(m)
            tool_results.append(m)
            _append_abundance(merged_rows, sid, m.get("metaphlan_abundance"), "metaphlan")
            post_violations.extend(check_skill_post("metaphlan", m))
            bandit.update("metaphlan", success=True, quality=float(m.get("classification_rate") or 0.5), match=0.7)

        if "microcafe" in tools:
            g = glm.run_microcafe(sample, upstream, tax_dir, ctx=ctx)
            art.update(g)
            tool_results.append(g)
            _append_abundance(merged_rows, sid, g.get("glm_abundance"), "microcafe")
            post_violations.extend(check_skill_post("microcafe", g))
            bandit.update("microcafe", success=True, quality=float(g.get("classification_rate") or 0.6), match=0.8)

        if "microrag" in tools:
            g = glm.run_microrag(sample, upstream, tax_dir, ctx=ctx)
            art.update(g)
            tool_results.append(g)
            _append_abundance(merged_rows, sid, g.get("glm_abundance"), "microrag")
            post_violations.extend(check_skill_post("microrag", g))
            bandit.update("microrag", success=True, quality=float(g.get("classification_rate") or 0.6), match=0.75)

        if len(tool_results) >= 2:
            fused = glm.fuse_taxonomy(tool_results)
            art["fusion"] = fused
            art["top_genera"] = fused.get("top_genera") or art.get("top_genera")
            art["classification_rate"] = fused.get("classification_rate", art.get("classification_rate"))
        else:
            for tr in tool_results:
                art["top_genera"] = list(dict.fromkeys(art.get("top_genera", []) + tr.get("top_genera", [])))
                art["classification_rate"] = max(float(art.get("classification_rate") or 0), float(tr.get("classification_rate") or 0))

        per_sample[sid] = art

    profile = outdir / "taxonomy_profile.tsv"
    profile.write_text("\n".join(merged_rows) + "\n", encoding="utf-8")
    (outdir / "taxonomy_routing.json").write_text(
        __import__("json").dumps(routing, indent=2), encoding="utf-8"
    )

    result: dict[str, Any] = {
        "taxonomy": per_sample,
        "taxonomy_profile": str(profile),
        "taxonomy_routing": routing,
    }
    error_posts = [v for v in post_violations if v.get("severity") == "error"]
    if error_posts:
        result["errors"] = [
            {"node": "taxonomy:post_contract", "error": v["message"], "classified": "logic"} for v in error_posts
        ]
    result["contract_post"] = post_violations

    # Biological interpretation of top taxa (contamination vs enrichment hypotheses)
    interpretation = _interpret_taxa(per_sample, state)
    interp_path = outdir / "taxonomy_interpretation.md"
    interp_path.write_text(interpretation["markdown"], encoding="utf-8")
    result["taxonomy_interpretation"] = interpretation
    result["taxonomy_interpretation_path"] = str(interp_path)
    return result


CONTAMINANT_HINTS = {
    "Pseudomonas": (
        "常见于试剂/环境或水源污染，亦可见于部分环境富集；"
        "需结合空白对照、试剂批次与宿主去除率判断 contamination vs biological enrichment。"
    ),
    "Staphylococcus": (
        "可能为皮肤来源污染或真实定植；检查采样与提取流程，并对照阴性对照。"
    ),
    "Ralstonia": "高丰度时常提示试剂污染，建议核查试剂空白。",
    "Bradyrhizobium": "试剂/环境常见背景菌，优先怀疑 contamination。",
}

GUT_MARKERS = {
    "Faecalibacterium",
    "Bacteroides",
    "Prevotella",
    "Bifidobacterium",
    "Roseburia",
    "Akkermansia",
    "Escherichia",
}


def _interpret_taxa(per_sample: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    bio = (state.get("artifacts") or {}).get("bio_reasoning") or {}
    disease = bio.get("disease_context")
    notes: list[dict[str, Any]] = []
    lines = ["# Taxonomy biological interpretation", ""]
    if disease:
        lines.append(f"Disease/phenotype context from Bio Reasoning: `{disease}`.")
        lines.append("")

    all_tops: list[str] = []
    for sid, art in per_sample.items():
        tops = list(art.get("top_genera") or [])
        all_tops.extend(tops)
        lines.append(f"## Sample `{sid}`")
        lines.append(f"- Top genera: {', '.join(tops) if tops else '(none)'}")
        for g in tops:
            if g in CONTAMINANT_HINTS:
                hyp = {
                    "sample": sid,
                    "genus": g,
                    "hypotheses": ["contamination", "environmental_origin", "biological_enrichment"],
                    "note": CONTAMINANT_HINTS[g],
                }
                notes.append(hyp)
                lines.append(f"- **{g}** 需鉴别: {CONTAMINANT_HINTS[g]}")
            elif g in GUT_MARKERS:
                lines.append(f"- **{g}**: 常见肠道相关属；结合差异检验与证据链解读，勿直接断言因果。")
        lines.append("")

    expected = set(bio.get("expected_markers") or [])
    found = expected & set(all_tops)
    missing = expected - set(all_tops)
    if expected:
        lines.append("## Expected markers (from Bio Reasoning)")
        lines.append(f"- Observed: {', '.join(sorted(found)) or '(none yet in top list)'}")
        lines.append(f"- Not in top genera: {', '.join(sorted(missing)) or '(none)'}")
        lines.append("")

    lines.append("解释仅基于丰度排序与领域启发式，需结合 QC、空白对照与统计显著性。")
    return {"notes": notes, "markdown": "\n".join(lines), "expected_observed": sorted(found)}


def _append_abundance(rows: list[str], sample_id: str, path: str | None, tool: str) -> None:
    if not path or not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines()[1:]:
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            rows.append(f"{sample_id}\t{parts[0]}\t{parts[1]}\t{tool}")
