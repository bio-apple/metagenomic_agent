"""Tests for 2026 proposal: bio RAG, evidence, quality, DAG export, tool decision."""

from pathlib import Path

from metagenomic_agent.agents.evidence import build_evidence_table, evidence_table_md
from metagenomic_agent.evaluation.quality_score import compute_quality_scores
from metagenomic_agent.execution.dag_export import export_workflow_dag
from metagenomic_agent.rag import retrieve, retrieve_multi
from metagenomic_agent.skills.decision import decide_taxonomy_tools


def test_bio_rag_gtdb_faecalibacterium():
    hits = retrieve("gtdb", "Faecalibacterium")
    assert hits
    assert "Faecalibacterium" in hits[0]["name"] or "Faecalibacterium" in str(hits[0].get("aliases"))


def test_bio_rag_card_and_kegg():
    assert retrieve("card", "Escherichia")
    assert retrieve("kegg", "butyrate")
    multi = retrieve_multi("Escherichia", dbs=["card", "vfdb"], top_k_per_db=1)
    assert multi["card"] or multi["vfdb"]


def test_evidence_table_contains_pmid():
    rows = build_evidence_table(
        ["Faecalibacterium", "Escherichia"],
        {"Faecalibacterium": "depleted_in_IBD", "Escherichia": "enriched_in_IBD"},
        "IBD gut biomarkers",
        mode="mock",
        cfg={"literature": {"online": False}},
    )
    assert rows
    assert any(r.get("pmid") for r in rows)
    md = evidence_table_md(rows)
    assert "PMID" in md or "pmid" in md.lower()
    assert "Faecalibacterium" in md or "Escherichia" in md


def test_quality_scores_overall():
    state = {
        "outdir": "/tmp",
        "config": {"pipeline": {"enable_assembly": False}},
        "artifacts": {
            "qc_host": {"S1": {"read_retention": 0.9, "host_fraction": 0.1}},
            "taxonomy": {"S1": {"classification_rate": 0.7}},
        },
    }
    q = compute_quality_scores(state)
    assert "Overall Score" in q["scores"]
    assert q["scores"]["Overall Score"] >= 50


def test_dag_export(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "user_query": "IBD",
        "run_id": "t1",
        "config": {"execution": {"engine": "langgraph"}},
        "dag": [
            {"id": "quality_control", "agent": "qc", "tools": ["fastp"], "depends_on": [], "status": "pending"},
            {
                "id": "taxonomy_profile",
                "agent": "taxonomy",
                "tools": ["kraken2"],
                "depends_on": ["quality_control"],
                "status": "pending",
            },
        ],
    }
    info = export_workflow_dag(state)
    assert Path(info["path"]).exists()
    assert (tmp_path / "workflow" / "dag.mmd").exists()


def test_tool_decision_low_memory():
    assert decide_taxonomy_tools({"memory_gb": 8, "n_samples": 10, "read_length": 150}) == ["kraken2"]
    assert decide_taxonomy_tools({"memory_gb": 64, "n_samples": 5, "read_length": 8000}) == ["microcafe"]
