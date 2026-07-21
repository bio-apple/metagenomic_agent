"""Development.docx Priority 1–3 coverage (v0.24): replan, MAG Flye/VAMB, stats reasoning."""

from pathlib import Path

from metagenomic_agent.agents import assembly_agent, statistics_agent
from metagenomic_agent.agents.bio_reasoning_agent import reason
from metagenomic_agent.agents.scientific_replan import apply_scientific_replan, should_scientific_replan
from metagenomic_agent.knowledge.domain_rag import detect_sample_environment, load_sops, retrieve_sops
from metagenomic_agent.stats.diagnostics import diagnose_abundance, simpson_index
from metagenomic_agent.tools import flye as flye_tool
from metagenomic_agent.tools.context import ToolContext


def test_wastewater_environment_and_sop():
    load_sops.cache_clear()
    assert detect_sample_environment("WWTP activated sludge ARG survey") == "wastewater"
    hits = retrieve_sops("wastewater sewage resistome")
    assert any(h.get("id") == "env_wastewater_prep" for h in hits)


def test_long_read_prefers_flye_and_vamb():
    bio = reason(
        "Nanopore long-read metagenomics MAG recovery",
        samples=[{"sample_id": "S1", "read_length_est": 5000}],
    )
    assert bio["assembler_preference"] == "flye"
    assert "vamb" in bio.get("binners_preference", [])
    assert bio["recommended_assay"] == "long_read_metagenomics"


def test_metatranscriptomics_assay():
    bio = reason("Gut metatranscriptomics of IBD flares")
    assert bio["recommended_assay"] == "metatranscriptomics"


def test_cohort_auto_mag():
    samples = [{"sample_id": f"S{i}", "group": "A" if i < 10 else "B"} for i in range(22)]
    bio = reason("Community profiling of large cohort", samples=samples)
    assert bio["enable_assembly"] is True


def test_scientific_replan_patches_taxonomy_and_assembly():
    state = {
        "outdir": "/tmp",
        "query": "IBD vs control",
        "mode": "mock",
        "config": {"pipeline": {}},
        "samples": [],
        "dag": [
            {
                "id": "taxonomy_profile",
                "agent": "taxonomy",
                "tools": ["kraken2"],
                "status": "done",
            }
        ],
        "critic": {
            "recommendations": [
                "Add MetaPhlAn for classification; enable MAG assembly and VAMB binning",
            ],
            "warnings": [],
        },
        "artifacts": {},
        "messages": [],
    }
    assert should_scientific_replan(state)
    out = apply_scientific_replan(state)
    assert out["artifacts"]["scientific_replan_count"] == 1
    tax = next(n for n in out["dag"] if n.get("agent") == "taxonomy")
    assert "metaphlan" in tax["tools"]
    assert out["config"]["pipeline"].get("enable_assembly") is True
    assert any(n.get("agent") == "assembly" for n in out["dag"])


def test_diagnostics_recommend_compositional_methods():
    matrix = {
        "c1": {"A": 0.5, "B": 0.5, "C": 0.0},
        "c2": {"A": 0.4, "B": 0.6, "C": 0.0},
        "t1": {"A": 0.1, "B": 0.1, "C": 0.8},
        "t2": {"A": 0.05, "B": 0.15, "C": 0.8},
    }
    groups = {"c1": "Control", "c2": "Control", "t1": "Case", "t2": "Case"}
    d = diagnose_abundance(matrix, groups)
    assert d["compositional"] is True
    assert "ancom_bc2" in d["recommended_diff_methods"] or "maaslin3" in d["recommended_diff_methods"]
    assert 0.0 <= simpson_index(matrix["c1"]) <= 1.0


def test_statistics_writes_simpson_and_diagnostics(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "mode": "mock",
        "config": {"statistics": {"demo_mode": True}},
        "samples": [],
        "artifacts": {},
    }
    out = statistics_agent.run(state)
    stats = out["statistics"]
    assert "abundance_diagnostics" in stats["methods"]
    assert "simpson_alpha" in stats["methods"]
    assert Path(stats["alpha_diversity"]).exists()
    header = Path(stats["alpha_diversity"]).read_text(encoding="utf-8").splitlines()[0]
    assert "simpson" in header
    assert (tmp_path / "diversity_analysis" / "abundance_diagnostics.json").exists()
    assert stats.get("diagnostics")


def test_flye_mock_and_mag_summary(tmp_path: Path):
    ctx = ToolContext(mode="mock", outdir=tmp_path)
    sample = {"sample_id": "LR1", "r1": str(tmp_path / "r.fq")}
    (tmp_path / "r.fq").write_text("@1\nACGT\n+\nIIII\n", encoding="utf-8")
    art = flye_tool.run(sample, {}, tmp_path / "asm", ctx=ctx)
    assert art["assembler"] == "flye"
    assert art.get("contigs")

    state = {
        "outdir": str(tmp_path / "run"),
        "mode": "mock",
        "config": {"pipeline": {"binners": ["metabat2", "vamb"]}, "cache": {"per_sample_assembly": False}},
        "samples": [sample],
        "artifacts": {
            "qc_host": {"LR1": {}},
            "bio_reasoning": {"assembler_preference": "flye"},
        },
    }
    (tmp_path / "run").mkdir()
    node = {"params": {"assembler": "flye", "binners": ["metabat2", "vamb"]}}
    result = assembly_agent.run(state, node)
    assert result.get("mag_summary")
    mag_json = Path(result["mag_summary"]).with_suffix(".json")
    # assembly writes mag_summary.json beside tsv
    assert (Path(state["outdir"]) / "mags" / "mag_summary.json").exists()
    assert "mag_summary_stats" in result
    assert result["mag_summary_stats"]["total_MAG"] >= 1
    _ = mag_json
