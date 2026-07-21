"""Domain RAG + Planner/Executor/QC-Critic/Reporter roles (v0.16)."""

from pathlib import Path

from metagenomic_agent.agents import critic_agent, executor_agent, planner_agent, reporter_agent
from metagenomic_agent.agents.bio_reasoning_agent import reason
from metagenomic_agent.knowledge.domain_rag import (
    detect_sample_environment,
    retrieve_sops,
    retrieve_tool_manuals,
)
from metagenomic_agent.tools.schemas import validate_tool_params


def test_retrieve_tool_manuals_kraken_gtdb_bakta_checkm():
    for tool in ("kraken2", "gtdbtk", "bakta", "checkm2"):
        hits = retrieve_tool_manuals(tool, tool=tool, top_k=1)
        assert hits and hits[0]["id"] == tool
        assert hits[0].get("docs")


def test_sop_16s_vs_shotgun_and_environments():
    assay = retrieve_sops("16S vs shotgun for pathway analysis", top_k=2)
    assert any(s["id"] == "assay_16s_vs_shotgun" for s in assay)
    assert detect_sample_environment("海洋海水菌群") == "ocean"
    assert detect_sample_environment("土壤根际微生物") == "soil"
    assert detect_sample_environment("IBD 肠道菌群") == "gut"
    soil = retrieve_sops("soil metagenome assembly", top_k=2)
    assert any(s["id"] == "env_soil_prep" for s in soil)


def test_bio_reasoning_cites_sop_and_manuals():
    bio = reason("分析肥胖患者肠道菌群变化与功能通路")
    assert bio.get("sample_environment") == "gut"
    assert bio.get("sop_ids")
    assert bio.get("tool_manual_ids") or any("tool_manual" in str(c.get("source")) for c in bio.get("citations") or [])


def test_gtdbtk_bakta_schemas():
    assert validate_tool_params(
        "gtdbtk", {"bins_dir": "results/bins", "threads": 8, "outdir": "results"}
    ).ok
    assert validate_tool_params(
        "bakta", {"input": "genome.fa", "db": "bakta_db", "threads": 4, "outdir": "results"}
    ).ok


def test_planner_executor_reporter(tmp_path: Path):
    state = {
        "input_path": str(tmp_path / "fq"),
        "outdir": str(tmp_path / "out"),
        "mode": "mock",
        "user_query": "soil shotgun MAG recovery",
        "run_id": "r16",
        "samples": [{"sample_id": "S1", "r1": "a.fq"}],
        "config": {"linux": {"threads": 4, "memory_gb": 16}, "paths": {}, "cache": {"enabled": False}},
        "dag": [
            {
                "id": "assembly_binning",
                "agent": "assembly",
                "tools": ["megahit", "checkm2", "gtdbtk"],
                "params": {},
                "status": "pending",
                "depends_on": [],
            }
        ],
        "artifacts": {
            "bio_reasoning": {
                "study_goal": "mag_recovery",
                "recommended_assay": "shotgun_metagenomics",
                "pipeline_steps": ["QC", "Assembly", "CheckM2", "GTDB-Tk"],
                "enable_assembly": True,
            },
            "router": {"primary_intent": "mag"},
            "tool_specialist": {"specialists": [{"tool": "checkm2", "params": {}}]},
        },
        "messages": [],
    }
    plan = planner_agent.run(state)
    assert (tmp_path / "out" / "planner" / "planner_plan.json").exists()
    assert plan["artifacts"]["planner"]["sample_environment"] == "soil"

    specs = executor_agent.prepare_submit_specs({**state, "artifacts": plan["artifacts"]})
    assert Path(specs["slurm"]).exists()
    assert Path(specs["k8s"]).exists()

    # Critic with CheckM failure
    crit_state = {
        **state,
        "artifacts": {
            **plan["artifacts"],
            "qc_host": {"S1": {"read_retention": 0.9, "host_fraction": 0.05, "Q30": 95, "Q20": 98}},
            "taxonomy": {"S1": {"classification_rate": 0.5, "top_genera": ["Bacteroides"]}},
            "assembly": {"S1": {"completeness": 40, "contamination": 12}},
        },
    }
    crit = critic_agent.run(crit_state)
    assert crit["critic"]["passed"] is False
    assert any("CheckM" in w or "completeness" in w for w in crit["critic"]["warnings"])

    rep = reporter_agent.run(
        {
            **crit_state,
            "artifacts": {**crit_state["artifacts"], **crit["artifacts"], "planner": plan["artifacts"]["planner"]},
            "critic": crit["critic"],
            "statistics": {"n_biomarkers": 2},
        }
    )
    assert (tmp_path / "out" / "reporter" / "biological_report.md").exists()
    assert rep["artifacts"]["reporter"]["role"] == "reporter"
