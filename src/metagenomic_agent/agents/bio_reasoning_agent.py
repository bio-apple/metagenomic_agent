"""Biological Reasoning Agent — requirement understanding before workflow planning.

Upgrades the stack from LLM+pipeline-wrapper to:
User → Requirement Understanding → Biological Reasoning → Workflow Planning → Tools → Interpretation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.knowledge.domain_rag import (
    detect_sample_environment,
    domain_context_block,
    manual_citations,
    retrieve_sops,
    retrieve_tool_manuals,
)
from metagenomic_agent.knowledge.workflow_rag import retrieve_workflow_snippets
from metagenomic_agent.messaging import append_msg, emit

COT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "bio_cot_examples.json"
BP_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "best_practices.md"

# Disease / phenotype cues → study framing
DISEASE_CUES: list[tuple[tuple[str, ...], str, list[str]]] = [
    (("ibd", "crohn", "colitis", "溃疡性", "克罗恩"), "IBD", ["Faecalibacterium", "Escherichia", "Roseburia"]),
    (("obes", "肥胖", "bmi", "adipos"), "obesity", ["Akkermansia", "Bacteroides", "Prevotella"]),
    (("diabet", "糖尿病", "t2d"), "type2_diabetes", ["Akkermansia", "Roseburia"]),
    (("crc", "colorectal", "结直肠", "colon cancer"), "CRC", ["Fusobacterium", "Bacteroides"]),
    (("autism", "asd", "自闭"), "ASD", ["Bacteroides", "Prevotella"]),
]

ASSAY_CUES = {
    "shotgun": ("shotgun_metagenomics", "Unbiased community + function; preferred for disease association."),
    "宏基因组": ("shotgun_metagenomics", "Unbiased community + function; preferred for disease association."),
    "16s": ("amplicon_16s", "Cheaper taxonomy; limited function — escalate to shotgun if pathways needed."),
    "amplicon": ("amplicon_16s", "Cheaper taxonomy; limited function — escalate to shotgun if pathways needed."),
}


def _detect_disease(query: str) -> tuple[str | None, list[str]]:
    q = query.lower()
    for keys, label, markers in DISEASE_CUES:
        if any(k in q for k in keys):
            return label, markers
    return None, []


def _detect_assay(query: str) -> tuple[str, str]:
    q = query.lower()
    for key, (assay, note) in ASSAY_CUES.items():
        if key in q:
            return assay, note
    # Default for disease / gut / microbiome queries
    if any(k in q for k in ("gut", "肠道", "stool", "fecal", "microbiom", "菌群", "disease", "肥胖", "ibd")):
        return (
            "shotgun_metagenomics",
            "Disease-associated gut microbiome questions typically need shotgun for taxonomy + function.",
        )
    return "shotgun_metagenomics", "Default to shotgun metagenomics unless amplicon is specified."


def _load_cot_library() -> list[dict[str, Any]]:
    if COT_PATH.exists():
        try:
            return json.loads(COT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def _match_cot(query: str) -> dict[str, Any] | None:
    q = query.lower()
    best = None
    best_score = 0
    for ex in _load_cot_library():
        score = sum(1 for t in ex.get("triggers") or [] if t.lower() in q)
        if score > best_score:
            best_score = score
            best = ex
    return best if best_score > 0 else None


def _study_goal(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ("biomarker", "标志", "差异", "vs", "对照", "case", "control", "变化")):
        return "disease_association_differential"
    if any(k in q for k in ("mag", "bin", "组装", "assembly", "genome")):
        return "mag_recovery"
    if any(k in q for k in ("function", "pathway", "功能", "kegg", "resistance", "耐药")):
        return "functional_profiling"
    if any(k in q for k in ("virus", "噬菌体", "phage", "virome")):
        return "viral_metagenomics"
    return "community_profiling"


def reason(query: str, samples: list[dict[str, Any]] | None = None, router: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pure reasoning over the user query (+ optional router hints)."""
    samples = samples or []
    router = router or {}
    goal = _study_goal(query)
    disease, markers = _detect_disease(query)
    assay, assay_note = _detect_assay(query)
    n = len(samples)
    long_reads = any(float(s.get("read_length_est") or 150) >= 1000 for s in samples)
    high_complexity = bool(disease) or "gut" in query.lower() or "肠道" in query or n >= 2

    enable_host = any(k in query.lower() for k in ("human", "gut", "stool", "fecal", "肠道", "宿主", "肥胖", "ibd")) or (
        (router.get("domains") or [None])[0] in {"human_gut", "clinical"} if router.get("domains") else True
    )
    enable_function = goal in {"disease_association_differential", "functional_profiling"} or any(
        k in query.lower() for k in ("function", "pathway", "功能", "机制")
    )
    # Disease association almost always benefits from functional layer
    if goal == "disease_association_differential":
        enable_function = True
    enable_statistics = goal == "disease_association_differential" or any(
        k in query.lower() for k in ("biomarker", "差异", "对照")
    )
    enable_assembly = goal == "mag_recovery" or any(k in query.lower() for k in ("mag", "assembly", "组装"))

    cot = _match_cot(query)
    assembler = "megahit" if high_complexity else "metaspades"
    if cot and cot.get("assembler"):
        assembler = cot["assembler"]

    # Force external KB retrieval (nf-core / SOP / tool manuals + best practices)
    wf_hits = retrieve_workflow_snippets(query, engine=None, top_k=3)
    sop_hits = retrieve_sops(query, top_k=3)
    manual_hits = retrieve_tool_manuals(query, top_k=3)
    env = detect_sample_environment(query)
    bp_excerpt = ""
    if BP_PATH.exists():
        bp_excerpt = BP_PATH.read_text(encoding="utf-8")[:800]

    citations = list((cot or {}).get("citations") or [])
    if not citations:
        citations = [
            {
                "source": "nf-co.re",
                "url": "https://nf-co.re/",
                "note": "Default community pipeline catalogue when no scenario CoT matched",
            }
        ]
    for h in wf_hits:
        citations.append(
            {
                "source": f"workflow_rag:{h.get('id')}",
                "url": "https://nf-co.re/",
                "note": h.get("title") or h.get("id"),
                "score": h.get("score"),
            }
        )
    for s in sop_hits:
        citations.append(
            {
                "source": f"sop:{s.get('id')}",
                "url": "",
                "note": s.get("title"),
                "score": s.get("score"),
            }
        )
    citations.extend(manual_citations(manual_hits))

    chain = list((cot or {}).get("chain") or [])
    if not chain:
        chain = [
            f"Infer study goal `{goal}` from the user query without inventing taxa.",
            f"Recommend assay `{assay}` with explicit justification.",
            "Select tools only when backed by CoT library or nf-core/workflow RAG citations.",
            "Record the full reasoning chain for human audit.",
        ]

    steps = [
        "Host removal" if enable_host else "QC without host filter",
        "Taxonomic profiling",
    ]
    if enable_function:
        steps.append("Functional profiling (pathways / AMR)")
    if enable_assembly:
        steps.append(f"Assembly & binning ({assembler})")
    if enable_statistics:
        steps.append("Differential abundance analysis")
    steps.append("Biological interpretation (grounded evidence)")
    steps.append("Interactive visualization & report")

    rationale = [
        f"Study goal inferred as `{goal}`.",
        f"Recommended assay: `{assay}` — {assay_note}",
        f"CoT example matched: `{(cot or {}).get('id') or 'generic_fallback'}`.",
    ]
    if disease:
        rationale.append(f"Disease/phenotype context: `{disease}`; watch markers {', '.join(markers)}.")
    rationale.append(
        f"Sample complexity heuristic → assembler preference `{assembler}` "
        f"(high_complexity={high_complexity}, n_samples={n}, long_reads={long_reads})."
    )
    if enable_statistics and not any(s.get("group") for s in samples):
        rationale.append("Differential analysis requested but groups missing — will escalate via HITL / demo_mode.")
    if bp_excerpt:
        rationale.append("Best-practices KB loaded for Supervisor handoff (see audit trail).")
    rationale.append(f"Sample environment inferred as `{env}` via domain SOP RAG.")
    if sop_hits:
        rationale.append("SOP hits: " + ", ".join(s.get("id", "") for s in sop_hits))
    if manual_hits:
        rationale.append("Tool manuals: " + ", ".join(m.get("id", "") for m in manual_hits))

    # Assay override from SOP when 16S explicitly preferred without function need
    for s in sop_hits:
        if s.get("id") == "assay_16s_vs_shotgun" and assay == "amplicon_16s":
            rationale.append("Assay SOP confirms 16S path; escalate to shotgun if pathways required.")

    next_experiments = []
    if disease == "obesity":
        next_experiments = [
            "Validate Akkermansia / SCFA producer shifts in independent cohort",
            "Pair metagenomics with metabolomics (SCFAs, bile acids)",
            "Consider dietary confounder adjustment (fiber, calories)",
        ]
    elif disease == "IBD":
        next_experiments = [
            "Confirm Faecalibacterium depletion / Escherichia enrichment with qPCR or culturomics",
            "Integrate mucosal vs stool if available",
        ]
    elif enable_statistics:
        next_experiments = [
            "Replicate differential taxa in held-out samples",
            "Follow up top pathways with targeted assays",
        ]

    return {
        "study_goal": goal,
        "disease_context": disease,
        "recommended_assay": assay,
        "assay_note": assay_note,
        "expected_markers": markers,
        "pipeline_steps": steps,
        "enable_host_filter": enable_host,
        "enable_function": enable_function,
        "enable_statistics": enable_statistics,
        "enable_assembly": enable_assembly,
        "assembler_preference": assembler,
        "high_complexity": high_complexity,
        "long_reads": long_reads,
        "n_samples": n,
        "rationale": rationale,
        "reasoning_chain": chain,
        "citations": citations,
        "cot_example_id": (cot or {}).get("id"),
        "workflow_rag_ids": [h.get("id") for h in wf_hits],
        "sop_ids": [s.get("id") for s in sop_hits],
        "tool_manual_ids": [m.get("id") for m in manual_hits],
        "sample_environment": env,
        "domain_context": domain_context_block(query),
        "next_experiments": next_experiments,
        "router_intent": router.get("primary_intent"),
        "router_domains": router.get("domains") or [],
        "policy": "cot_must_cite_external_kb_no_ungrounded_tool_choice",
        "best_practices_excerpt": bp_excerpt[:400] if bp_excerpt else "",
    }


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    router = (state.get("artifacts") or {}).get("router") or {}
    # router_agent may store under router_decision file only — also check keys
    if not router:
        path = Path(state["outdir"]) / "router_decision.json"
        if path.exists():
            try:
                router = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                router = {}

    bio = reason(state.get("user_query") or "", state.get("samples") or [], router)

    # Require citations — block empty citation list (anti reasoning-hallucination)
    if not bio.get("citations"):
        bio["citations"] = [
            {"source": "nf-co.re", "url": "https://nf-co.re/", "note": "mandatory fallback citation"}
        ]
        bio["citation_enforced"] = True

    outdir = Path(state["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "bio_reasoning.json").write_text(json.dumps(bio, indent=2, ensure_ascii=False), encoding="utf-8")

    audit = {
        "cot_example_id": bio.get("cot_example_id"),
        "reasoning_chain": bio.get("reasoning_chain"),
        "citations": bio.get("citations"),
        "workflow_rag_ids": bio.get("workflow_rag_ids"),
        "policy": bio.get("policy"),
    }
    (outdir / "bio_reasoning_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md = [
        "# Biological Reasoning",
        "",
        f"- **Study goal**: `{bio['study_goal']}`",
        f"- **Assay**: `{bio['recommended_assay']}` — {bio['assay_note']}",
        f"- **Disease/phenotype**: `{bio.get('disease_context') or 'n/a'}`",
        f"- **Assembler preference**: `{bio['assembler_preference']}`",
        f"- **CoT example**: `{bio.get('cot_example_id') or 'generic'}`",
        "",
        "## Reasoning chain (audit)",
        "",
    ]
    for i, step in enumerate(bio.get("reasoning_chain") or [], 1):
        md.append(f"{i}. {step}")
    md.extend(["", "## Citations (required)", ""])
    for c in bio.get("citations") or []:
        md.append(f"- [{c.get('source')}]({c.get('url')}) — {c.get('note')}")
    md.extend(["", "## Recommended pipeline", ""])
    for i, step in enumerate(bio["pipeline_steps"], 1):
        md.append(f"{i}. {step}")
    md.extend(["", "## Rationale", ""])
    for r in bio["rationale"]:
        md.append(f"- {r}")
    if bio.get("next_experiments"):
        md.extend(["", "## Suggested follow-up experiments", ""])
        for x in bio["next_experiments"]:
            md.append(f"- {x}")
    (outdir / "bio_reasoning.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Structured HITL options for study design (multi-choice)
    hitl_options = [
        {
            "id": "study_design",
            "question": (
                f"Bio Reasoning recommends goal=`{bio['study_goal']}`, assay=`{bio['recommended_assay']}`, "
                f"function analysis={'on' if bio['enable_function'] else 'off'}, "
                f"differential analysis={'on' if bio['enable_statistics'] else 'off'}. Please confirm:"
            ),
            "choices": [
                {"key": "A", "label": "Continue with reasoned plan", "action": "accept_plan"},
                {"key": "B", "label": "Taxonomy only (skip function/differential)", "action": "taxonomy_only"},
                {"key": "C", "label": "Force-enable MAG assembly", "action": "force_assembly"},
            ],
            "default": "A",
        }
    ]
    if bio["enable_statistics"] and not any(s.get("group") for s in state.get("samples") or []):
        hitl_options.append(
            {
                "id": "missing_groups",
                "question": "Differential analysis is planned but samples lack group metadata:",
                "choices": [
                    {"key": "A", "label": "Continue with demo/synthetic groups", "action": "demo_mode"},
                    {"key": "B", "label": "Skip statistics nodes", "action": "skip_stats"},
                    {"key": "C", "label": "Abort and supply --metadata", "action": "abort_for_metadata"},
                ],
                "default": "A",
            }
        )

    memory = ContextMemory(Path(state["outdir"]) / "context")
    memory.update(bio_reasoning=bio)
    memory.append_history(f"bio_reasoning:{bio['study_goal']}:{bio['recommended_assay']}")

    # Human-readable pending lines (backward compatible)
    hitl_pending = list(state.get("hitl_pending") or [])
    hitl_pending.append(
        f"[BioReasoning] goal={bio['study_goal']} assay={bio['recommended_assay']} "
        f"steps={len(bio['pipeline_steps'])} — confirm study design (A/B/C)"
    )

    amsg = emit("bio_reasoning", "supervisor", "plan", bio)
    from metagenomic_agent.knowledge.reasoning_log import log_decision

    arts = {
        **state.get("artifacts", {}),
        "bio_reasoning": bio,
        "hitl_options": hitl_options,
        "bio_reasoning_path": str(outdir / "bio_reasoning.md"),
    }
    reason_patch = log_decision(
        {**state, "artifacts": arts},
        "bio_reasoning",
        f"Use {bio['recommended_assay']} / assembler={bio.get('assembler_preference')}",
        f"goal={bio['study_goal']}; cot={bio.get('cot_example_id')}; citations={len(bio.get('citations') or [])}",
    )
    arts = {**arts, **(reason_patch.get("artifacts") or {})}
    return {
        "hitl_pending": hitl_pending,
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [f"Bio Reasoning: goal={bio['study_goal']} assay={bio['recommended_assay']}"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }
