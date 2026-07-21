"""Benchmark helpers for RAG, evidence coverage, and ordination sanity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.evaluation.metrics import evaluate_run
from metagenomic_agent.rag import retrieve
from metagenomic_agent.rag.embeddings import semantic_retrieve
from metagenomic_agent.stats.ordination import classical_mds


def rag_hit_rate(queries: list[str], db: str = "gtdb") -> float:
    hits = sum(1 for q in queries if retrieve(db, q, top_k=1))
    return hits / max(len(queries), 1)


def semantic_hit_rate(queries: list[str]) -> float:
    hits = sum(1 for q in queries if semantic_retrieve(q, top_k=1))
    return hits / max(len(queries), 1)


def evidence_pmid_coverage(evidence_table: list[dict[str, Any]]) -> float:
    if not evidence_table:
        return 0.0
    ok = sum(1 for r in evidence_table if r.get("pmid") and str(r["pmid"]) not in {"kb", "mock", ""})
    return ok / len(evidence_table)


def ordination_smoke() -> dict[str, Any]:
    dist = [
        [0.0, 0.2, 0.5],
        [0.2, 0.0, 0.4],
        [0.5, 0.4, 0.0],
    ]
    coords, eigs = classical_mds(dist, n_components=2)
    return {"n_points": len(coords), "eigenvalues": eigs, "ok": len(coords) == 3}


def run_benchmark_suite(outdir: Path | None = None) -> dict[str, Any]:
    from metagenomic_agent.evaluation.cami_toy import evaluate_cami_toy, write_cami_report
    from metagenomic_agent.evaluation.self_heal_fpr import evaluate_self_heal_fpr

    queries = ["Faecalibacterium", "Escherichia", "Akkermansia", "butyrate", "TEM-1"]
    report: dict[str, Any] = {
        "rag_hit_rate_gtdb": rag_hit_rate(["Faecalibacterium", "Escherichia", "Akkermansia"]),
        "rag_hit_rate_kegg": rag_hit_rate(["butyrate", "kinase"], db="kegg"),
        "semantic_hit_rate": semantic_hit_rate(queries),
        "ordination": ordination_smoke(),
        "cami_toy": evaluate_cami_toy(outdir),
        "self_heal_fpr": evaluate_self_heal_fpr(),
    }
    if outdir and outdir.exists():
        report["evaluate_run"] = evaluate_run(outdir, golden={"biomarker_genera": ["Faecalibacterium", "Escherichia"]})
        report["cami_toy"] = write_cami_report(outdir)
        ev = outdir / "evidence" / "evidence_table.json"
        if ev.exists():
            import json

            report["evidence_pmid_coverage"] = evidence_pmid_coverage(json.loads(ev.read_text()))
    report["passed"] = (
        report["rag_hit_rate_gtdb"] >= 0.6
        and report["semantic_hit_rate"] >= 0.4
        and report["ordination"]["ok"]
        and bool(report["cami_toy"].get("passed"))
        and float(report["self_heal_fpr"]["trigger"]["fpr"]) == 0.0
        and float(report["self_heal_fpr"]["action"]["fpr_after_safe_policy"]) == 0.0
    )
    return report
