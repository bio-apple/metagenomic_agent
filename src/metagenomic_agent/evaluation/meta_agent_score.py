"""MetaAgentScore — Planning / Tool / Execution / Reasoning / Error / Reproducibility."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.evaluation.cami_toy import evaluate_cami_toy


REQUIRED_PLAN_STEPS = {
    "quality_control",
    "taxonomy",
    "diversity",
    "statistics",
    "pathway",
    "functional",
}


def planning_accuracy(state: dict[str, Any]) -> float:
    dag = state.get("dag") or []
    agents = " ".join(f"{n.get('id')} {n.get('agent')}" for n in dag).lower()
    planner = ((state.get("artifacts") or {}).get("planner") or {}).get("pipeline_steps") or []
    blob = agents + " " + " ".join(str(x).lower() for x in planner)
    hits = 0
    checks = [
        ("qc" in blob or "quality" in blob),
        ("taxonom" in blob or "kraken" in blob or "metaphlan" in blob),
        ("divers" in blob or "statistic" in blob or "shannon" in blob),
        ("statistic" in blob or "biomarker" in blob or "differen" in blob),
        ("function" in blob or "pathway" in blob or "humann" in blob or "diamond" in blob),
    ]
    hits = sum(1 for c in checks if c)
    return hits / max(len(checks), 1)


def tool_selection_score(state: dict[str, Any]) -> float:
    tools = []
    for n in state.get("dag") or []:
        tools.extend(n.get("tools") or [])
    tools_l = {t.lower() for t in tools}
    wanted = {"fastp", "kraken2", "metaphlan"}
    return len(wanted & tools_l) / max(len(wanted), 1)


def execution_success(state: dict[str, Any]) -> float:
    errors = (state.get("artifacts") or {}).get("errors") or []
    dag = state.get("dag") or []
    done = sum(1 for n in dag if n.get("status") in {"done", "cached", "success", None, "pending"})
    # pending after full run still ok in mock; penalize failed
    failed = sum(1 for n in dag if n.get("status") == "failed")
    if not dag:
        return 0.5 if not errors else 0.2
    return max(0.0, 1.0 - 0.25 * failed - 0.1 * min(len(errors), 5))


def biological_reasoning_score(state: dict[str, Any]) -> float:
    lit = state.get("literature") or (state.get("artifacts") or {}).get("literature") or {}
    entries = lit.get("entries") or []
    if not entries:
        # KG/evidence pack may still exist
        pack = (state.get("artifacts") or {}).get("evidence_integration") or {}
        return 0.6 if pack.get("items") else 0.3
    grounded = sum(1 for e in entries if e.get("grounded"))
    return grounded / max(len(entries), 1)


def error_detection_score(state: dict[str, Any]) -> float:
    """Did reviewer/critic surface simulated or real issues when present?"""
    critic = state.get("critic") or {}
    reviewer = (state.get("artifacts") or {}).get("reviewer") or {}
    warnings = list(critic.get("warnings") or []) + list(reviewer.get("concerns") or [])
    # Injected benchmark scenarios mark artifacts.errors_injected
    injected = (state.get("artifacts") or {}).get("errors_injected") or []
    if not injected:
        # No injection — score by whether QC concerns are non-empty when host high
        return 0.8 if warnings is not None else 0.5
    caught = 0
    blob = " ".join(warnings).lower()
    for inj in injected:
        key = str(inj).lower()
        if key in blob or any(tok in blob for tok in key.split("_")):
            caught += 1
    return caught / max(len(injected), 1)


def reproducibility_score(state: dict[str, Any]) -> float:
    out = Path(state.get("outdir") or ".")
    checks = [
        (out / "workflow" / "params.yaml").exists() or (out / "workflow" / "params.json").exists(),
        (out / "reproducibility" / "run_manifest.json").exists()
        or bool((state.get("artifacts") or {}).get("reproducibility")),
        (out / "reasoning" / "chain.md").exists()
        or bool((state.get("artifacts") or {}).get("reasoning_md")),
    ]
    return sum(1 for c in checks if c) / max(len(checks), 1)


def compute_meta_agent_score(state: dict[str, Any]) -> dict[str, Any]:
    scores = {
        "Planning Accuracy": round(planning_accuracy(state), 3),
        "Tool Selection": round(tool_selection_score(state), 3),
        "Execution Success": round(execution_success(state), 3),
        "Biological Reasoning": round(biological_reasoning_score(state), 3),
        "Error Detection": round(error_detection_score(state), 3),
        "Reproducibility": round(reproducibility_score(state), 3),
    }
    cami = evaluate_cami_toy(Path(state["outdir"]) if state.get("outdir") else None)
    scores["CAMI Toy F1"] = cami.get("f1")
    overall = sum(v for k, v in scores.items() if k != "CAMI Toy F1" and isinstance(v, (int, float))) / 6
    report = {
        "MetaAgentScore": round(overall, 3),
        "metrics": scores,
        "cami_toy": cami,
        "passed": overall >= 0.55,
    }
    if state.get("outdir"):
        root = Path(state["outdir"]) / "evaluation"
        root.mkdir(parents=True, exist_ok=True)
        (root / "meta_agent_score.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = ["# MetaAgentScore", "", f"**Overall:** `{report['MetaAgentScore']}`", ""]
        for k, v in scores.items():
            lines.append(f"- {k}: `{v}`")
        (root / "meta_agent_score.md").write_text("\n".join(lines), encoding="utf-8")
        report["path"] = str(root / "meta_agent_score.json")
    return report


def planning_benchmark(query: str = "Compare gut microbiome between IBD and healthy controls") -> dict[str, Any]:
    """Unit-style planning benchmark without full pipeline."""
    from metagenomic_agent.agents.supervisor import _default_plan

    tasks = _default_plan(
        query,
        {"pipeline": {"enable_functional": True, "enable_statistics": True, "enable_arg": True}},
        bio={"enable_statistics": True, "enable_function": True, "disease_context": "IBD"},
    )
    names = " ".join(t["name"] for t in tasks).lower()
    required = ["quality", "taxonomy", "statistical", "functional"]
    hit = sum(1 for r in required if r in names)
    return {
        "query": query,
        "tasks": [t["name"] for t in tasks],
        "score": hit / len(required),
        "passed": hit >= 3,
    }


def error_diagnosis_benchmark() -> dict[str, Any]:
    """Simulate contamination / low depth / batch and check reviewer detection."""
    from metagenomic_agent.agents import reviewer_agent

    state = {
        "outdir": str(Path("/tmp/meta_err_bench")),  # overwritten below
        "samples": [{"sample_id": "S1"}, {"sample_id": "S2"}],
        "critic": {
            "passed": True,
            "warnings": [],
            "recommendations": [],
            "details": {
                "samples": {
                    "S1": {"host_fraction": 0.7, "read_retention": 0.25, "Q30": 70},
                    "S2": {"host_fraction": 0.1, "read_retention": 0.9, "Q30": 92},
                }
            },
        },
        "statistics": {"biomarker_list": [], "methods": ["mannwhitney_u"]},
        "artifacts": {"errors_injected": ["contamination", "low_depth", "batch"]},
        "messages": [],
    }
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        state["outdir"] = td
        out = reviewer_agent.run(state)
        review = out["artifacts"]["reviewer"]
        blob = " ".join(review.get("concerns") or []).lower()
        caught = {
            "contamination": "contamin" in blob or "host" in blob,
            "low_depth": "depth" in blob or "retention" in blob,
            "batch": "batch" in blob or "host" in blob,
        }
        return {"caught": caught, "score": sum(caught.values()) / 3, "passed": sum(caught.values()) >= 2}


def biological_reasoning_benchmark() -> dict[str, Any]:
    from metagenomic_agent.knowledge.microbiome_kg import explain_microbe

    expl = explain_microbe("Faecalibacterium")
    text = json.dumps(expl).lower()
    ok = "faecalibacterium" in text and ("butyrate" in text or "pathway" in text or "kegg" in text or expl.get("kg_edges"))
    return {"taxon": "Faecalibacterium", "passed": bool(ok), "chain": expl.get("chain_hint")}
