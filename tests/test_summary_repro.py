"""Summary-driven context + reproducible workflow export."""

from __future__ import annotations

import json
from pathlib import Path

from metagenomic_agent.coordinator.memory import ContextMemory
from metagenomic_agent.coordinator.summary import (
    build_pipeline_summary,
    fasta_assembly_stats,
    get_llm_context,
    write_pipeline_summary,
)
from metagenomic_agent.report.reproducibility import write_reproducibility_bundle
from metagenomic_agent.report.workflow_export import export_executed_workflows, resolve_run_seed


def test_fasta_n50(tmp_path: Path):
    fa = tmp_path / "c.fa"
    # lengths 100, 80, 20 → total 200, N50 should be 100
    fa.write_text(">a\n" + ("A" * 100) + "\n>b\n" + ("C" * 80) + "\n>c\n" + ("G" * 20) + "\n")
    stats = fasta_assembly_stats(fa)
    assert stats is not None
    assert stats["n_contigs"] == 3
    assert stats["total_bp"] == 200
    assert stats["n50"] == 100
    assert stats["note"] == "lengths_only_no_sequence_in_context"


def test_pipeline_summary_metadata_only(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "run_id": "t1",
        "mode": "mock",
        "samples": [{"sample_id": "S1"}],
        "dag": [{"id": "qc", "agent": "qc", "tools": ["fastp"], "status": "done"}],
        "artifacts": {
            "qc_host": {
                "S1": {
                    "Q30": 95,
                    "read_retention": 0.9,
                    "host_fraction": 0.05,
                    "reads_before": 1_000_000,
                    "reads_after": 900_000,
                    "status": "PASS",
                    "fastp_json": None,
                }
            },
            "taxonomy": {"S1": {"top_genera": ["Bacteroides", "Faecalibacterium"], "classification_rate": 0.7}},
            "statistics": {
                "biomarker_list": [{"genus": "Faecalibacterium", "p_value": 0.01, "q_value": 0.05, "direction": "down"}]
            },
        },
    }
    summary = write_pipeline_summary(state)
    assert (tmp_path / "context" / "pipeline_summary.json").exists()
    assert summary["qc"]["mean_Q30"] == 95
    assert summary["policy"] == "summary_driven_no_raw_sequences"
    ctx = get_llm_context({**state, "artifacts": {**state["artifacts"], "pipeline_summary": summary}})
    assert "Q30" in ctx
    assert "ACGT" not in ctx  # no sequence content
    assert "@" not in ctx or "sample_id" in ctx


def test_memory_llm_safe_view(tmp_path: Path):
    mem = ContextMemory(tmp_path / "ctx")
    mem.update(pipeline_summary={"qc": {"mean_Q30": 90}}, run_seed=42)
    view = mem.llm_safe_view()
    assert view["run_seed"] == 42
    assert view["pipeline_summary"]["qc"]["mean_Q30"] == 90


def test_reproducible_export(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "run_id": "repro1",
        "mode": "mock",
        "input_path": str(tmp_path / "fastq"),
        "user_query": "IBD biomarker",
        "config": {"reproducibility": {"seed": 12345}, "linux": {"threads": 4}},
        "dag": [
            {
                "id": "qc",
                "agent": "qc",
                "tools": ["fastp"],
                "params": {},
                "status": "done",
                "depends_on": [],
            }
        ],
        "artifacts": {"pipeline_summary": {"path": str(tmp_path / "context" / "pipeline_summary.json")}},
    }
    assert resolve_run_seed(state) == 12345
    paths = export_executed_workflows(state)
    assert Path(paths["nextflow"]).exists()
    assert Path(paths["snakemake"]).exists()
    seeds = json.loads(Path(paths["seeds"]).read_text())
    assert seeds["run_seed"] == 12345
    nf = Path(paths["nextflow"]).read_text()
    assert "params.seed = 12345" in nf
    assert "AGENT_ORCHESTRATE" in nf
    smk = Path(paths["snakemake"]).read_text()
    assert "SEED = 12345" in smk
    assert Path(paths["config_snapshot"]).exists()

    bundle = write_reproducibility_bundle(state)
    assert Path(bundle["manifest"]).exists()
    man = json.loads(Path(bundle["manifest"]).read_text())
    assert man["run_seed"] == 12345
    assert "reproducible.nf" in bundle["reproducible_nf"]


def test_build_summary_with_assembly_n50(tmp_path: Path):
    fa = tmp_path / "asm.fa"
    fa.write_text(">c1\n" + ("A" * 50) + "\n>c2\n" + ("T" * 50) + "\n")
    state = {
        "outdir": str(tmp_path),
        "run_id": "a1",
        "mode": "mock",
        "samples": [{"sample_id": "S1"}],
        "dag": [],
        "artifacts": {
            "assembly": {
                "S1": {
                    "assembler": "megahit",
                    "contigs": str(fa),
                    "n_bins": 2,
                    "completeness": 80.0,
                    "contamination": 2.0,
                }
            }
        },
    }
    s = build_pipeline_summary(state)
    assert s["assembly_mags"]["samples"][0]["assembly"]["n50"] == 50
    assert s["assembly_mags"]["mean_completeness"] == 80.0
