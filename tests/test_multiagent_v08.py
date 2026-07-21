"""Tests for multi-agent Router / Specialist / Validator / workflow RAG / XAI."""

from pathlib import Path

from metagenomic_agent.agents import plan_validator, router_agent, tool_specialist
from metagenomic_agent.evaluation.xai import leave_one_out_importance
from metagenomic_agent.knowledge.domain_kb import infer_domains, recommend_tools
from metagenomic_agent.knowledge.workflow_rag import retrieve_workflow_snippets


def test_infer_virus_domain():
    assert "virus" in infer_domains("Analyze phage virome with ViWrap")
    tools = recommend_tools("viral metagenome phage discovery")
    names = [t["tool"] for t in tools]
    assert "viwrap" in names or "phabox" in names


def test_router_agent(tmp_path: Path):
    state = {
        "user_query": "IBD gut biomarker discovery",
        "outdir": str(tmp_path),
        "samples": [{"sample_id": "S1", "read_length_est": 150}],
        "config": {"linux": {"memory_gb": 32}},
        "artifacts": {},
        "messages": [],
    }
    out = router_agent.run(state)
    assert out["artifacts"]["router"]["intent"]["primary_intent"] in {
        "biomarker_discovery",
        "taxonomy_profiling",
    }
    assert (tmp_path / "router_decision.json").exists()


def test_tool_specialist_commands(tmp_path: Path):
    state = {
        "user_query": "gut taxonomy",
        "outdir": str(tmp_path),
        "mode": "mock",
        "config": {"paths": {"kraken2_db": "db"}, "linux": {"threads": 4}},
        "dag": [{"id": "taxonomy_profile", "agent": "taxonomy", "tools": ["kraken2"], "depends_on": []}],
        "artifacts": {"router": {"recommended_tools": [{"tool": "kraken2"}], "domains": ["prokaryote_taxonomy"]}},
        "messages": [],
    }
    out = tool_specialist.run(state)
    specs = out["artifacts"]["tool_specialist"]["specialists"]
    assert specs and specs[0].get("command")


def test_plan_validator_flags_empty_dag(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "user_query": "test",
        "mode": "mock",
        "config": {"hitl": {"auto_confirm": True}, "pipeline": {}},
        "dag": [],
        "samples": [],
        "artifacts": {},
        "messages": [],
        "hitl_pending": [],
        "hitl_auto_confirm": True,
    }
    out = plan_validator.run(state)
    assert out["artifacts"]["plan_validation"]["passed"] is False


def test_workflow_rag():
    hits = retrieve_workflow_snippets("nf-core mag assembly binning", engine="nextflow")
    assert hits


def test_xai_importance():
    matrix = {
        "c1": {"Faecalibacterium": 0.05, "Escherichia": 0.2},
        "c2": {"Faecalibacterium": 0.04, "Escherichia": 0.22},
        "h1": {"Faecalibacterium": 0.2, "Escherichia": 0.03},
        "h2": {"Faecalibacterium": 0.22, "Escherichia": 0.02},
    }
    groups = {"c1": "IBD", "c2": "IBD", "h1": "Control", "h2": "Control"}
    rows = leave_one_out_importance(matrix, groups)
    assert rows[0]["feature"] in {"Escherichia", "Faecalibacterium"}
