"""Literature-informed features from paper/ corpus (v0.26)."""

from pathlib import Path

from metagenomic_agent.agents.bio_reasoning_agent import reason
from metagenomic_agent.agents import resistance_agent
from metagenomic_agent.evaluation.virus_tools_lite import run_virus_tool_scenarios
from metagenomic_agent.knowledge.domain_rag import detect_sample_environment, load_sops, retrieve_sops
from metagenomic_agent.tools import functional as functional_tool
from metagenomic_agent.tools.context import ToolContext
from metagenomic_agent.tools import arg as arg_tools


def test_environments_from_literature():
    assert detect_sample_environment("infant skin microbiome catalog") == "skin"
    assert detect_sample_environment("agricultural air metagenomic diversity") == "air"
    assert detect_sample_environment("gut mycobiome fungi catalog") == "mycobiome"
    assert detect_sample_environment("nasopharyngeal respiratory mNGS") == "respiratory"


def test_sops_include_literature_protocols():
    load_sops.cache_clear()
    ids = {s["id"] for s in load_sops()}
    for need in (
        "fecal_functional_annotation",
        "env_skin_prep",
        "env_air_prep",
        "env_mycobiome",
        "clinical_respiratory_mngs",
        "virus_identification_benchmark",
    ):
        assert need in ids
    hits = retrieve_sops("fecal DIAMOND functional annotation e-value")
    assert any(h["id"] == "fecal_functional_annotation" for h in hits)


def test_amrfinder_and_virus_suite(tmp_path: Path):
    ctx = ToolContext(mode="mock", outdir=tmp_path)
    fa = tmp_path / "c.fa"
    fa.write_text(">x\nATGCATGC\n", encoding="utf-8")
    amr = arg_tools.run_amrfinderplus(str(fa), tmp_path / "amr", ctx, "S1")
    assert amr["tool"] == "amrfinderplus" and amr["n_hits"] >= 1
    rep = run_virus_tool_scenarios(tmp_path / "vbench")
    assert rep["ok"] and "genomad" in rep["callers"]


def test_functional_megan_lite(tmp_path: Path):
    ctx = ToolContext(mode="mock", outdir=tmp_path)
    sample = {"sample_id": "F1", "r1": str(tmp_path / "r.fq")}
    (tmp_path / "r.fq").write_text("@1\nACGT\n+\nIIII\n", encoding="utf-8")
    art = functional_tool.run(sample, {}, tmp_path / "fn", ctx=ctx)
    assert Path(art["megan_lite_taxonomy"]).exists()
    assert art.get("diamond_evalue") == "1e-5"


def test_mycobiome_and_resistance_agent(tmp_path: Path):
    bio = reason("Characterize gut mycobiome fungal signatures in IBD")
    assert bio["recommended_assay"] == "mycobiome_shotgun"
    state = {
        "outdir": str(tmp_path),
        "mode": "mock",
        "config": {},
        "samples": [{"sample_id": "S1", "r1": str(tmp_path / "a.fq")}],
        "artifacts": {"qc_host": {"S1": {}}, "assembly": {}},
        "messages": [],
    }
    (tmp_path / "a.fq").write_text("@1\nACGT\n+\nIIII\n", encoding="utf-8")
    out = resistance_agent.run(state)
    assert "amrfinderplus" in out["artifacts"]["resistance"]["tools"]
    sample_rep = out["artifacts"]["resistance"]["per_sample"]["S1"]
    assert "amrfinder" in sample_rep or sample_rep.get("tool")
