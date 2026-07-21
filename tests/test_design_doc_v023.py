"""Design-doc feature coverage (v0.23): resistance, evidence, reviewer, KG, MetaAgentScore."""

from pathlib import Path

from metagenomic_agent.agents import (
    code_agent,
    evidence_agent,
    reflection_agent,
    resistance_agent,
    reviewer_agent,
)
from metagenomic_agent.agents.supervisor import _default_plan
from metagenomic_agent.evaluation.meta_agent_score import (
    biological_reasoning_benchmark,
    compute_meta_agent_score,
    error_diagnosis_benchmark,
    planning_benchmark,
)
from metagenomic_agent.knowledge.microbiome_kg import build_kg, explain_microbe


def test_default_plan_includes_resistance_and_evidence_tasks():
    tasks = _default_plan(
        "IBD vs healthy ARG virulence",
        {"pipeline": {"enable_arg": True, "enable_functional": True}},
        bio={"enable_statistics": True, "enable_function": True},
    )
    names = {t["name"] for t in tasks}
    assert "resistance_virulence" in names
    assert "evidence_integration" in names
    assert "scientific_review" in names


def test_kg_and_explain():
    kg = build_kg()
    assert kg["n_nodes"] > 0 and kg["n_edges"] > 0
    expl = explain_microbe("Faecalibacterium")
    assert expl["taxon"] == "Faecalibacterium"


def test_resistance_evidence_reviewer_reflection_code(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "mode": "mock",
        "config": {},
        "samples": [{"sample_id": "S1", "r1": str(tmp_path / "a.fq")}],
        "artifacts": {
            "qc_host": {"S1": {}},
            "statistics": {
                "biomarker_list": [
                    {"genus": "Faecalibacterium", "direction": "enriched_in_Control", "p_value": 0.01, "q_value": 0.05, "log2fc": -1.2}
                ],
                "methods": ["mannwhitney_u"],
            },
            "literature": {"entries": [{"genus": "Faecalibacterium", "grounded": True, "interpretation": "butyrate", "papers": []}]},
        },
        "critic": {
            "passed": True,
            "warnings": [],
            "recommendations": [],
            "details": {"samples": {"S1": {"host_fraction": 0.1, "read_retention": 0.9, "Q30": 95}}},
        },
        "literature": {"entries": [{"genus": "Faecalibacterium", "grounded": True, "interpretation": "butyrate", "papers": []}]},
        "statistics": {
            "biomarker_list": [
                {"genus": "Faecalibacterium", "direction": "enriched_in_Control", "p_value": 0.01, "q_value": 0.05, "log2fc": -1.2}
            ],
            "methods": ["mannwhitney_u"],
        },
        "messages": [],
        "dag": [{"id": "quality_control", "agent": "qc", "tools": ["fastp"], "status": "done"}],
    }
    (tmp_path / "a.fq").write_text("@1\nACGT\n+\nIIII\n", encoding="utf-8")
    (tmp_path / "diversity_analysis").mkdir()
    (tmp_path / "diversity_analysis" / "genus_matrix.tsv").write_text(
        "sample\tFaecalibacterium\nS1\t0.2\n", encoding="utf-8"
    )
    (tmp_path / "biomarkers").mkdir()
    (tmp_path / "biomarkers" / "biomarkers.tsv").write_text(
        "genus\tq_value\nFaecalibacterium\t0.05\n", encoding="utf-8"
    )

    r = resistance_agent.run(state)
    assert (tmp_path / "resistance_virulence" / "resistance_report.md").exists()
    state = {**state, "artifacts": {**state["artifacts"], **r["artifacts"]}}

    e = evidence_agent.run(state)
    assert (tmp_path / "evidence_integration" / "evidence_pack.md").exists()
    state = {**state, "artifacts": {**state["artifacts"], **e["artifacts"]}}

    rev = reviewer_agent.run(state)
    assert rev["artifacts"]["reviewer"]["confidence"] > 0
    state = {**state, "artifacts": {**state["artifacts"], **rev["artifacts"]}, "critic": rev["critic"]}

    ref = reflection_agent.run(state)
    assert (tmp_path / "reflection" / "reflection.md").exists()
    state = {**state, "artifacts": {**state["artifacts"], **ref["artifacts"]}}

    code = code_agent.run(state)
    assert code["artifacts"]["code_agent"]["ok"] is True

    score = compute_meta_agent_score(state)
    assert "MetaAgentScore" in score
    assert (tmp_path / "evaluation" / "meta_agent_score.json").exists()


def test_benchmarks():
    assert planning_benchmark()["passed"]
    assert error_diagnosis_benchmark()["passed"]
    assert biological_reasoning_benchmark()["passed"]
