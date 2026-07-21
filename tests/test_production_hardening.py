"""Production hardening: step cache, CoT citations, resource estimate, lite dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from metagenomic_agent.agents.bio_reasoning_agent import reason, run as bio_run
from metagenomic_agent.execution.resource_estimate import estimate_resources
from metagenomic_agent.execution.step_cache import StepCache, cache_key
from metagenomic_agent.report.interactive import write_interactive_dashboard


def test_cot_citations_required():
    bio = reason("土壤宏基因组中的低丰度病毒")
    assert bio.get("cot_example_id") == "cot_soil_low_virus"
    assert bio.get("reasoning_chain")
    assert bio.get("citations")
    assert any("biostars" in str(c.get("url", "")).lower() or "nf-co" in str(c.get("url", "")).lower() for c in bio["citations"])


def test_bio_audit_file(tmp_path: Path):
    state = {
        "user_query": "肥胖患者肠道菌群",
        "outdir": str(tmp_path),
        "samples": [{"sample_id": "S1"}],
        "artifacts": {},
        "messages": [],
        "hitl_pending": [],
    }
    out = bio_run(state)
    assert (tmp_path / "bio_reasoning_audit.json").exists()
    audit = json.loads((tmp_path / "bio_reasoning_audit.json").read_text())
    assert audit["citations"]
    assert audit["reasoning_chain"]
    assert out["artifacts"]["bio_reasoning"]["cot_example_id"]


def test_step_cache_roundtrip(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "mode": "mock",
        "input_path": "/tmp/x",
        "samples": [{"sample_id": "S1"}],
    }
    node = {"id": "taxonomy_profile", "agent": "taxonomy", "tools": ["kraken2"], "params": {}}
    cache = StepCache(tmp_path, enabled=True)
    key = cache.store(node, state, {"taxonomy": {"S1": {"top_genera": ["Bacteroides"]}}, "taxonomy_profile": str(tmp_path / "t.tsv")}, tmp_path)
    (tmp_path / "t.tsv").write_text("ok\n")
    assert key
    assert cache_key(node, state) == key
    hit = cache.lookup(node, state, {})
    assert hit is not None


def test_resource_estimate_warns_on_assembly():
    state = {
        "mode": "docker",
        "samples": [{"sample_id": f"S{i}"} for i in range(4)],
        "dag": [{"agent": "assembly", "status": "pending"}, {"agent": "taxonomy", "status": "pending"}],
        "config": {"linux": {"memory_gb": 16, "threads": 8}, "execution": {"engine": "nextflow"}},
    }
    est = estimate_resources(state)
    assert est["est_total_wall_hours"] > 0
    assert est["resume"]["nextflow_resume"] is True
    assert any("Assembly" in w or "memory" in w.lower() for w in est["warnings"])


def test_lite_dashboard(tmp_path: Path):
    div = tmp_path / "diversity_analysis"
    bio = tmp_path / "biomarkers"
    fig = tmp_path / "report" / "figures"
    div.mkdir(parents=True)
    bio.mkdir(parents=True)
    fig.mkdir(parents=True)
    (div / "genus_matrix.tsv").write_text("sample\tA\nS1\t0.1\nS2\t0.2\n")
    (div / "alpha_diversity.tsv").write_text("sample\tgroup\tshannon\trichness\nS1\tA\t2\t10\nS2\tB\t3\t12\n")
    (div / "beta_diversity.tsv").write_text("sample_a\tsample_b\tbray_curtis\nS1\tS2\t0.3\n")
    (bio / "biomarkers.tsv").write_text(
        "genus\tlog2fc\tp_value\tq_value\tdirection\nA\t1\t0.01\t0.02\tup\n"
    )
    (fig / "pcoa.json").write_text(json.dumps({"points": [{"sample": "S1", "PC1": 0, "PC2": 0, "group": "A"}]}))
    state = {
        "outdir": str(tmp_path),
        "run_id": "lite1",
        "user_query": "test",
        "samples": [{"sample_id": "S1"}, {"sample_id": "S2"}],
        "config": {"visualization": {"lite": True, "default_q": 0.1}},
        "artifacts": {
            "statistics": {
                "genus_matrix": str(div / "genus_matrix.tsv"),
                "alpha_diversity": str(div / "alpha_diversity.tsv"),
                "beta_diversity": str(div / "beta_diversity.tsv"),
                "biomarkers": str(bio / "biomarkers.tsv"),
                "groups": {"S1": "A", "S2": "B"},
                "biomarker_list": [{"genus": "A", "log2fc": 1, "p_value": 0.01, "q_value": 0.02}],
            }
        },
    }
    paths = write_interactive_dashboard(state, default_q=0.1)
    html = Path(paths["dashboard_root"]).read_text()
    assert "on-demand" in html or "lite" in html
    assert "FIGS =" not in html  # not fully embedded
    assert (tmp_path / "report" / "figures" / "dashboard_summary.json").exists()
    assert (tmp_path / "report" / "figures" / "composition.plotly.json").exists()
