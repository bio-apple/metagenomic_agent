"""v0.22: CAMI toy, vector memory, R export, Web UI."""

from pathlib import Path

from fastapi.testclient import TestClient

from metagenomic_agent.api.server import app
from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.evaluation.benchmarks import run_benchmark_suite
from metagenomic_agent.evaluation.cami_toy import evaluate_cami_toy, score_taxonomy
from metagenomic_agent.stats.export_for_r import export_r_bundle


def test_cami_toy_self_and_score():
    m = evaluate_cami_toy(None)
    assert m["passed"] is True
    assert m["f1"] >= 0.99
    s = score_taxonomy({"Faecalibacterium", "Bacteroides", "UnknownGenus"})
    assert "Faecalibacterium" in s["tp"]
    assert "UnknownGenus" in s["fp"]


def test_benchmark_suite_includes_cami():
    report = run_benchmark_suite(None)
    assert "cami_toy" in report
    assert report["cami_toy"]["passed"]


def test_memory_retrieve(tmp_path: Path):
    mem = ContextMemory(tmp_path / "context")
    mem.append_history("Used Kraken2 for fast IBD taxonomy profiling")
    mem.append_history("Assembly skipped due to HITL")
    mem.index_document("plan", "Planner chose MEGAHIT for high complexity gut samples")
    hits = mem.retrieve("Kraken2 IBD taxonomy", top_k=2)
    assert hits
    assert hits[0]["score"] > 0


def test_r_export(tmp_path: Path):
    matrix = {
        "S1": {"Faecalibacterium": 0.4, "Escherichia": 0.1},
        "S2": {"Faecalibacterium": 0.1, "Escherichia": 0.5},
    }
    groups = {"S1": "Control", "S2": "IBD"}
    out = export_r_bundle(matrix, groups, tmp_path / "r_export", try_run=False)
    assert Path(out["run_deseq2"]).exists()
    assert Path(out["run_maaslin2"]).exists()
    assert Path(out["run_ancombc"]).exists()
    assert Path(out["feature_counts"]).exists()


def test_web_ui_and_chat():
    client = TestClient(app)
    r = client.get("/ui")
    assert r.status_code == 200
    assert "Metagenomic Research Copilot" in r.text
    r2 = client.get("/")
    assert r2.status_code == 200
    chat = client.post("/chat", json={"question": "Faecalibacterium IBD"})
    assert chat.status_code == 200
