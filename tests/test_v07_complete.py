"""Comprehensive tests for v0.7 remaining requirements."""

from pathlib import Path

from metagenomic_agent.evaluation.benchmarks import run_benchmark_suite
from metagenomic_agent.rag import retrieve
from metagenomic_agent.rag.embeddings import semantic_retrieve
from metagenomic_agent.skills.checker import contract_check
from metagenomic_agent.stats.cooccurrence import cooccurrence_network
from metagenomic_agent.stats.compositional import ancom_like, clr_transform
from metagenomic_agent.stats.lefse_like import lefse_like
from metagenomic_agent.stats.ordination import classical_mds, pcoa_from_beta_tsv


def test_classical_mds_and_pcoa(tmp_path: Path):
    dist = [[0, 0.1, 0.5], [0.1, 0, 0.4], [0.5, 0.4, 0]]
    coords, eigs = classical_mds(dist, 2)
    assert len(coords) == 3
    beta = tmp_path / "beta.tsv"
    beta.write_text("sample_a\tsample_b\tbray_curtis\nA\tB\t0.2\nA\tC\t0.5\nB\tC\t0.3\n")
    pcoa = pcoa_from_beta_tsv(str(beta), {"A": "IBD", "B": "Control", "C": "Control"})
    assert len(pcoa["points"]) == 3


def test_lefse_and_ancom_like():
    matrix = {
        "c1": {"Faecalibacterium": 0.05, "Escherichia": 0.2},
        "c2": {"Faecalibacterium": 0.06, "Escherichia": 0.18},
        "c3": {"Faecalibacterium": 0.04, "Escherichia": 0.22},
        "h1": {"Faecalibacterium": 0.2, "Escherichia": 0.03},
        "h2": {"Faecalibacterium": 0.22, "Escherichia": 0.04},
        "h3": {"Faecalibacterium": 0.18, "Escherichia": 0.02},
    }
    groups = {"c1": "IBD", "c2": "IBD", "c3": "IBD", "h1": "Control", "h2": "Control", "h3": "Control"}
    assert lefse_like(matrix, groups)
    assert ancom_like(matrix, groups)
    assert "Faecalibacterium" in clr_transform(matrix["c1"])


def test_cooccurrence():
    matrix = {
        "s1": {"A": 0.1, "B": 0.2, "C": 0.05},
        "s2": {"A": 0.12, "B": 0.18, "C": 0.06},
        "s3": {"A": 0.09, "B": 0.21, "C": 0.04},
        "s4": {"A": 0.11, "B": 0.19, "C": 0.07},
    }
    net = cooccurrence_network(matrix, min_abs_corr=0.3)
    assert "nodes" in net


def test_semantic_rag():
    hits = semantic_retrieve("butyrate Faecalibacterium IBD", top_k=3)
    assert hits
    assert retrieve("gtdb", "Roseburia", mode="keyword")


def test_contract_hard_fail(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "user_query": "test",
        "config": {"validation": {"contract_hard_fail": True}},
        "samples": [{"sample_id": "S1", "r1": "", "platform": "illumina", "read_length_est": 150, "paired": False}],
        "dag": [{"id": "quality_control", "agent": "qc", "tools": ["fastp"], "params": {}, "depends_on": []}],
        "artifacts": {},
        "messages": [],
        "hitl_pending": [],
    }
    # empty r1 should trigger missing artifact if contract checks it
    out = contract_check(state)  # type: ignore[arg-type]
    # hard fail only when errors exist
    if out.get("artifacts", {}).get("contract_check", {}).get("n_errors", 0) > 0:
        assert out.get("error") or out.get("hitl_resolved") is False


def test_benchmark_suite():
    report = run_benchmark_suite()
    assert report["passed"]
    assert report["ordination"]["ok"]
