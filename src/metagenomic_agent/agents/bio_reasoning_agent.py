"""Biological Reasoning Agent — requirement understanding before workflow planning.

Upgrades the stack from LLM+pipeline-wrapper to:
User → Requirement Understanding → Biological Reasoning → Workflow Planning → Tools → Interpretation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.messaging import append_msg, emit

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

    assembler = "megahit" if high_complexity else "metaspades"
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
    ]
    if disease:
        rationale.append(f"Disease/phenotype context: `{disease}`; watch markers {', '.join(markers)}.")
    rationale.append(
        f"Sample complexity heuristic → assembler preference `{assembler}` "
        f"(high_complexity={high_complexity}, n_samples={n}, long_reads={long_reads})."
    )
    if enable_statistics and not any(s.get("group") for s in samples):
        rationale.append("Differential analysis requested but groups missing — will escalate via HITL / demo_mode.")

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
        "next_experiments": next_experiments,
        "router_intent": router.get("primary_intent"),
        "router_domains": router.get("domains") or [],
        "policy": "bio_reasoning_before_workflow_planning",
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

    outdir = Path(state["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "bio_reasoning.json").write_text(json.dumps(bio, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        "# Biological Reasoning",
        "",
        f"- **Study goal**: `{bio['study_goal']}`",
        f"- **Assay**: `{bio['recommended_assay']}` — {bio['assay_note']}",
        f"- **Disease/phenotype**: `{bio.get('disease_context') or 'n/a'}`",
        f"- **Assembler preference**: `{bio['assembler_preference']}`",
        "",
        "## Recommended pipeline",
        "",
    ]
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
                f"Bio Reasoning 建议目标=`{bio['study_goal']}`，assay=`{bio['recommended_assay']}`，"
                f"功能分析={'开' if bio['enable_function'] else '关'}，"
                f"差异分析={'开' if bio['enable_statistics'] else '关'}。请确认："
            ),
            "choices": [
                {"key": "A", "label": "按推理计划继续", "action": "accept_plan"},
                {"key": "B", "label": "仅分类学（跳过功能/差异）", "action": "taxonomy_only"},
                {"key": "C", "label": "强制开启 MAG 组装", "action": "force_assembly"},
            ],
            "default": "A",
        }
    ]
    if bio["enable_statistics"] and not any(s.get("group") for s in state.get("samples") or []):
        hitl_options.append(
            {
                "id": "missing_groups",
                "question": "差异分析已规划但样本无 group 元数据：",
                "choices": [
                    {"key": "A", "label": "使用 demo/synthetic 分组继续", "action": "demo_mode"},
                    {"key": "B", "label": "跳过统计节点", "action": "skip_stats"},
                    {"key": "C", "label": "中止并补充 --metadata", "action": "abort_for_metadata"},
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
    return {
        "hitl_pending": hitl_pending,
        "artifacts": {
            **state.get("artifacts", {}),
            "bio_reasoning": bio,
            "hitl_options": hitl_options,
            "bio_reasoning_path": str(outdir / "bio_reasoning.md"),
        },
        "messages": state.get("messages", [])
        + [f"Bio Reasoning: goal={bio['study_goal']} assay={bio['recommended_assay']}"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }
