"""Development.docx remaining Priority 2–5 coverage (v0.25)."""

from pathlib import Path

from metagenomic_agent.agents import assembly_agent, critic_agent, literature_agent, mag_agent, statistics_agent
from metagenomic_agent.agents.scientific_replan import apply_scientific_replan, should_scientific_replan
from metagenomic_agent.knowledge.microbiome_kg import build_kg, opposing_evidence, subgraph_for_taxon
from metagenomic_agent.rag import load_index
from metagenomic_agent.stats.association import run_association_suite
from metagenomic_agent.stats.batch_effect import batch_pca_dominance, residualize_by_batch
from metagenomic_agent.stats.unifrac import unifrac_summary, weighted_unifrac
from metagenomic_agent.tools import busco as busco_tool
from metagenomic_agent.tools import das_tool as das_tool_mod
from metagenomic_agent.tools.context import ToolContext


def test_das_tool_and_busco_mock(tmp_path: Path):
    ctx = ToolContext(mode="mock", outdir=tmp_path)
    bins = tmp_path / "bins"
    bins.mkdir()
    (bins / "a.bin.1.fa").write_text(">c1\nATGCATGC\n", encoding="utf-8")
    das = das_tool_mod.run_das_tool("S1", str(tmp_path / "c.fa"), {"metabat": str(bins)}, tmp_path / "das", ctx)
    assert das["binner_refinement"] == "das_tool"
    assert Path(das["bins_dir"]).exists()
    bus = busco_tool.run_busco(das["bins_dir"], tmp_path / "busco", ctx, "S1")
    assert bus["busco_complete"] >= 50


def test_assembly_includes_busco_in_mag_summary(tmp_path: Path):
    sample = {"sample_id": "S1", "r1": str(tmp_path / "r.fq")}
    (tmp_path / "r.fq").write_text("@1\nACGT\n+\nIIII\n", encoding="utf-8")
    state = {
        "outdir": str(tmp_path / "run"),
        "mode": "mock",
        "config": {"pipeline": {"binners": ["metabat2", "vamb"]}, "cache": {"per_sample_assembly": False}},
        "samples": [sample],
        "artifacts": {"qc_host": {"S1": {}}, "bio_reasoning": {"assembler_preference": "megahit"}},
    }
    (tmp_path / "run").mkdir()
    out = assembly_agent.run(state, {"params": {"assembler": "megahit", "binners": ["metabat2", "vamb"]}})
    tsv = Path(out["mag_summary"]).read_text(encoding="utf-8")
    assert "busco_complete" in tsv.splitlines()[0]
    assert out["mag_summary_stats"]["refinement"] == "das_tool"
    assert "busco" in out["mag_summary_stats"]["quality_tools"]


def test_mag_agent_facade(tmp_path: Path):
    sample = {"sample_id": "M1", "r1": str(tmp_path / "r.fq")}
    (tmp_path / "r.fq").write_text("@1\nACGT\n+\nIIII\n", encoding="utf-8")
    state = {
        "outdir": str(tmp_path / "mag"),
        "mode": "mock",
        "config": {"cache": {"per_sample_assembly": False}},
        "samples": [sample],
        "artifacts": {"qc_host": {"M1": {}}, "bio_reasoning": {}},
    }
    (tmp_path / "mag").mkdir()
    out = mag_agent.run(state)
    assert out["artifacts"]["mag"]["agent"] == "mag_discovery"


def test_unifrac_and_association():
    matrix = {
        "c1": {"Faecalibacterium": 0.4, "Bacteroides": 0.6},
        "c2": {"Faecalibacterium": 0.35, "Bacteroides": 0.65},
        "t1": {"Faecalibacterium": 0.1, "Escherichia": 0.9},
        "t2": {"Faecalibacterium": 0.05, "Escherichia": 0.95},
    }
    groups = {"c1": "Control", "c2": "Control", "t1": "Case", "t2": "Case"}
    d = weighted_unifrac(matrix["c1"], matrix["t1"])
    assert 0 <= d <= 1
    uni = unifrac_summary(matrix)
    assert uni["n_samples"] == 4
    cov = {"c1": {"age": 40}, "c2": {"age": 42}, "t1": {"age": 50}, "t2": {"age": 55}}
    assoc = run_association_suite(matrix, groups, covariates=cov)
    assert assoc["mixed"] or assoc["ml"] or assoc["linear"]


def test_batch_effect_correction():
    # Strong batch structure on PC1 (many samples per batch)
    matrix = {
        "a1": {"X": 0.95, "Y": 0.05},
        "a2": {"X": 0.92, "Y": 0.08},
        "a3": {"X": 0.90, "Y": 0.10},
        "b1": {"X": 0.05, "Y": 0.95},
        "b2": {"X": 0.08, "Y": 0.92},
        "b3": {"X": 0.10, "Y": 0.90},
    }
    batch = {s: ("B1" if s.startswith("a") else "B2") for s in matrix}
    diag = batch_pca_dominance(matrix, batch, r2_warn=0.15)
    assert diag["pc1_batch_r2"] >= 0.15
    assert diag["suspect"] is True
    adj = residualize_by_batch(matrix, batch)
    assert set(adj) == set(matrix)


def test_stats_writes_unifrac_and_assoc(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "mode": "mock",
        "config": {"statistics": {"demo_mode": True}},
        "samples": [
            {"sample_id": "case_1", "group": "IBD", "age": 40, "batch": "P1"},
            {"sample_id": "case_2", "group": "IBD", "age": 45, "batch": "P1"},
            {"sample_id": "case_3", "group": "IBD", "age": 50, "batch": "P2"},
            {"sample_id": "ctrl_1", "group": "Control", "age": 41, "batch": "P2"},
            {"sample_id": "ctrl_2", "group": "Control", "age": 43, "batch": "P1"},
            {"sample_id": "ctrl_3", "group": "Control", "age": 47, "batch": "P2"},
        ],
        "artifacts": {},
    }
    out = statistics_agent.run(state)
    stats = out["statistics"]
    assert "weighted_unifrac_lite" in stats["methods"]
    assert Path(stats["beta_unifrac"]).exists()
    assert stats.get("associations") is not None


def test_critic_flags_batch_and_replan():
    state = {
        "outdir": "/tmp",
        "mode": "mock",
        "user_query": "IBD biomarkers",
        "config": {},
        "samples": [],
        "artifacts": {
            "statistics": {
                "n_biomarkers": 1,
                "methods": ["mannwhitney_u"],
                "diagnostics": {"compositional": True},
                "batch_effect": {"suspect": True, "pc1_batch_r2": 0.6},
            }
        },
        "messages": [],
        "dag": [{"id": "statistics", "agent": "statistics", "status": "done"}],
        "critic": {},
    }
    # critic needs outdir
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        state["outdir"] = td
        out = critic_agent.run(state)
        assert any("batch" in w.lower() or "PCA" in w for w in out["critic"]["warnings"])
        state["critic"] = out["critic"]
        assert should_scientific_replan(state)
        replanned = apply_scientific_replan(state)
        assert replanned["config"]["statistics"].get("correct_batch") is True


def test_kg_resistance_and_opposing():
    build_kg.cache_clear()
    load_index.cache_clear()
    kg = build_kg()
    assert any(e.get("relation") == "confers_resistance" for e in kg["edges"])
    opp = opposing_evidence("Faecalibacterium", "IBD")
    assert opp["conflicts"] or opp["supporting"]
    sub = subgraph_for_taxon("Escherichia")
    assert sub["n_nodes"] >= 1


def test_literature_confidence_fields(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "mode": "mock",
        "user_query": "IBD gut microbiome",
        "config": {"interpretation": {"require_grounding": True}},
        "artifacts": {
            "bio_reasoning": {"disease_context": "IBD"},
            "statistics": {
                "biomarker_list": [
                    {"genus": "Faecalibacterium", "direction": "enriched_in_Control", "q_value": 0.01}
                ]
            },
        },
        "messages": [],
    }
    out = literature_agent.run(state)
    entries = out["literature"]["entries"]
    assert entries
    assert "confidence" in entries[0]
    assert "evidence" in entries[0]
