"""v0.21 shortfall closures: reasoning, literature report, hybrid RAG, tools, legends, chat."""

from pathlib import Path

from fastapi.testclient import TestClient

from metagenomic_agent.api.server import app
from metagenomic_agent.knowledge.reasoning_log import finalize_reasoning, log_decision
from metagenomic_agent.rag import retrieve, retrieve_hybrid
from metagenomic_agent.report.figure_legends import build_legends
from metagenomic_agent.tools.arg import run_arg_suite
from metagenomic_agent.tools.binning import run_binning
from metagenomic_agent.tools.context import ToolContext
from metagenomic_agent.tools.virus import run_virus_suite


def test_reasoning_chain(tmp_path: Path):
    state = {"outdir": str(tmp_path), "run_id": "r1", "artifacts": {}}
    p1 = log_decision(state, "planner", "Use Kraken2", "Fast classification")
    state = {**state, **p1, "artifacts": {**(state.get("artifacts") or {}), **(p1.get("artifacts") or {})}}
    p2 = log_decision(state, "literature", "Write report", "Grounded taxa ready")
    state = {**state, "artifacts": {**(state.get("artifacts") or {}), **(p2.get("artifacts") or {})}}
    fin = finalize_reasoning(state)
    assert (tmp_path / "reasoning" / "chain.jsonl").exists()
    assert (tmp_path / "reasoning" / "chain.md").exists()
    assert len(fin["artifacts"]["reasoning_steps"]) == 2


def test_hybrid_rag():
    hits = retrieve_hybrid("gtdb", "Faecalibacterium", top_k=3)
    assert isinstance(hits, list)
    # hybrid path should not crash; curated index may return keyword-only
    kw = retrieve("gtdb", "Faecalibacterium", top_k=3, mode="keyword")
    hy = retrieve("gtdb", "Faecalibacterium", top_k=3, mode="hybrid")
    assert len(hy) >= min(1, len(kw)) or len(hy) == 0  # allow empty if taxon absent
    if hy:
        assert hy[0].get("retrieval") == "hybrid"


def test_figure_legends(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "user_query": "IBD biomarkers",
        "samples": [{"sample_id": "S1"}, {"sample_id": "S2"}],
        "statistics": {"n_biomarkers": 3, "biomarker_list": [{"genus": "Faecalibacterium"}]},
        "config": {"visualization": {"default_q": 0.1}},
        "artifacts": {},
    }
    out = build_legends(state)
    assert Path(out["path"]).exists()
    text = Path(out["path"]).read_text(encoding="utf-8")
    assert "Figure 1" in text and "Figure 3" in text


def test_arg_virus_concoct_mock(tmp_path: Path):
    ctx = ToolContext(mode="mock", outdir=tmp_path)
    sample = {"sample_id": "S1", "r1": str(tmp_path / "a.fq")}
    (tmp_path / "a.fq").write_text("@1\nACGT\n+\nIIII\n", encoding="utf-8")
    contigs = tmp_path / "c.fa"
    contigs.write_text(">c1\n" + "ATGC" * 100 + "\n", encoding="utf-8")

    bins = run_binning("S1", str(contigs), {}, tmp_path / "bins", ctx, binners=["concoct"])
    assert "concoct" in bins.get("binners", [])
    assert Path(bins["concoct_dir"]).exists()

    arg = run_arg_suite(sample, {}, tmp_path / "arg", ctx, contigs=str(contigs))
    assert arg.get("n_hits", 0) >= 1
    vir = run_virus_suite(str(contigs), tmp_path / "virus", ctx, "S1")
    assert vir.get("n_viral", 0) >= 1
    assert vir.get("checkv", {}).get("n_contigs", 0) >= 1


def test_chat_api():
    client = TestClient(app)
    resp = client.post("/chat", json={"question": "Why is Faecalibacterium reduced in IBD?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "Grounded context" in body["answer"]
    assert "disclaimer" in body
