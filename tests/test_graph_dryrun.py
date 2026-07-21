from pathlib import Path

from metagenomic_agent.config_loader import load_config
from metagenomic_agent.evaluation import evaluate_run, precision_at_k
from metagenomic_agent.graph import run_pipeline
from metagenomic_agent.state import AgentState

from conftest import write_tiny_fastq


def _initial(fq: Path, out: Path, query: str) -> AgentState:
    cfg = load_config(
        overrides={
            "mode": "mock",
            "pipeline": {"enable_assembly": False},
            "hitl": {"auto_confirm": True},
            "statistics": {"demo_mode": True},
        }
    )
    return {
        "user_query": query,
        "input_path": str(fq),
        "outdir": str(out),
        "mode": "mock",
        "config": cfg,
        "samples": [],
        "metadata_path": None,
        "tasks": [],
        "dag": [],
        "artifacts": {},
        "messages": [],
        "agent_messages": [],
        "validation": None,
        "critic": None,
        "literature": None,
        "statistics": None,
        "retry_count": 0,
        "max_retries": 2,
        "hitl_pending": [],
        "hitl_auto_confirm": True,
        "hitl_resolved": False,
        "report_path": None,
        "error": None,
        "run_id": "test0001",
    }


def test_graph_dryrun_mock(tmp_path: Path):
    fq = tmp_path / "fastq"
    write_tiny_fastq(fq / "gut_R1.fastq")
    write_tiny_fastq(fq / "gut_R2.fastq")
    out = tmp_path / "out"
    final = run_pipeline(
        _initial(
            fq,
            out,
            "Analyze shotgun metagenomic samples from IBD patients and healthy controls. Identify microbial biomarkers.",
        )
    )
    assert final.get("report_path")
    assert Path(final["report_path"]).exists()
    assert (out / "quality_report.html").exists()
    assert (out / "taxonomy_profile.tsv").exists()
    assert (out / "functional_profile.tsv").exists()
    assert (out / "diversity_analysis" / "alpha_diversity.tsv").exists()
    assert (out / "biomarkers" / "biomarkers.tsv").exists()
    assert (out / "literature_summary" / "literature_summary.md").exists()
    assert (out / "report" / "methods.md").exists()
    assert "Mann-Whitney" in (out / "report" / "methods.md").read_text() or "mannwhitney" in (
        out / "report" / "methods.md"
    ).read_text().lower()
    assert (out / "report" / "reproduce.sh").exists()
    assert "--query" in (out / "report" / "reproduce.sh").read_text()
    assert (out / "logs" / "events.jsonl").exists()
    assert (out / "contract_check.json").exists()
    assert (out / "reproducibility" / "meta_agent.cwl").exists()
    assert (out / "evidence" / "evidence_table.md").exists()
    assert (out / "workflow" / "dag.json").exists()
    assert (out / "quality" / "quality_scores.json").exists()
    assert (out / "report" / "manuscript" / "manuscript_draft.md").exists()
    assert (out / "report" / "figures" / "manifest.json").exists()
    assert final.get("critic") is not None
    assert final.get("literature") is not None
    assert final.get("agent_messages") is not None


def test_supervisor_plan_json(tmp_path: Path):
    fq = tmp_path / "fastq"
    write_tiny_fastq(fq / "S_R1.fastq")
    write_tiny_fastq(fq / "S_R2.fastq")
    out = tmp_path / "out"
    final = run_pipeline(_initial(fq, out, "Find microbial signatures associated with inflammatory disease."))
    assert (out / "supervisor_plan.json").exists()
    assert final.get("tasks")


def test_golden_evaluation(tmp_path: Path):
    fq = tmp_path / "fastq"
    write_tiny_fastq(fq / "gut_R1.fastq")
    write_tiny_fastq(fq / "gut_R2.fastq")
    out = tmp_path / "out"
    run_pipeline(_initial(fq, out, "IBD biomarkers"))
    report = evaluate_run(out, golden={"biomarker_genera": ["Faecalibacterium", "Escherichia"]})
    assert report["passed"]
    assert report["biomarker_precision_at_5"] >= 0.0
    assert precision_at_k(["Faecalibacterium", "X"], ["Faecalibacterium"], k=1) == 1.0
