"""Bio QC chain + table-bound hallucination guardrails (v0.18)."""

from pathlib import Path

from metagenomic_agent.agents import critic_agent
from metagenomic_agent.knowledge.evidence_chain import build_claim
from metagenomic_agent.knowledge.grounded_interp import (
    assert_stats_from_table,
    grounded_interpretation_bundle,
    sanitize_interpretation_text,
    table_bound_universe,
    write_grounded_interp,
)
from metagenomic_agent.validators.bio_qc import (
    check_mag_qc,
    check_taxonomy_qc,
    classify_mag_quality,
    run_bio_qc_chain,
)


def test_checkm_high_quality_gate():
    assert classify_mag_quality(95, 2) == "high"
    assert classify_mag_quality(70, 8) == "medium"
    assert classify_mag_quality(40, 12) == "low"
    hq = check_mag_qc(completeness=92, contamination=3, sample_id="S1")
    assert hq["high_quality"] is True
    assert hq["ok"] is True
    mq = check_mag_qc(completeness=60, contamination=8, sample_id="S1")
    assert mq["tier"] == "medium"
    assert any("high-quality" in w or "90" in w for w in mq["warnings"])
    bad = check_mag_qc(completeness=40, contamination=15, sample_id="S1")
    assert bad["ok"] is False


def test_taxonomy_unclassified_gate():
    ok = check_taxonomy_qc(classification_rate=0.8, unclassified_fraction=0.2, sample_id="S1")
    assert ok["ok"] is True
    bad = check_taxonomy_qc(classification_rate=0.2, unclassified_fraction=0.8, sample_id="S1")
    assert bad["ok"] is False
    assert any("unclassified" in w for w in bad["warnings"])
    assert any("database" in r.lower() or "confidence" in r.lower() for r in bad["recommendations"])


def test_bio_qc_chain_and_critic(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "user_query": "MAG QC",
        "config": {
            "validation": {
                "mag_high_completeness": 90,
                "mag_high_contamination": 5,
                "min_classification_rate": 0.3,
                "max_unclassified_fraction": 0.5,
            }
        },
        "samples": [{"sample_id": "S1"}],
        "artifacts": {
            "qc_host": {"S1": {"read_retention": 0.9, "host_fraction": 0.05, "Q30": 95, "Q20": 98}},
            "taxonomy": {
                "S1": {
                    "classification_rate": 0.15,
                    "unclassified_fraction": 0.85,
                    "top_genera": ["Bacteroides"],
                }
            },
            "assembly": {"S1": {"completeness": 40, "contamination": 12, "n_bins": 2}},
        },
        "messages": [],
    }
    chain = run_bio_qc_chain(state)
    assert chain["ok"] is False
    assert chain["mag_tiers"]["S1"] == "low"
    crit = critic_agent.run(state)
    assert crit["critic"]["passed"] is False
    assert (tmp_path / "critic" / "bio_qc_chain.json").exists()
    blob = " ".join(crit["critic"]["warnings"])
    assert "unclassified" in blob or "classification" in blob
    assert "CheckM" in blob or "completeness" in blob or "tier" in blob


def test_table_bound_stats_guardrail(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "config": {"interpretation": {"require_grounding": True, "require_evidence_chain": True}},
        "artifacts": {
            "statistics": {
                "biomarker_list": [
                    {
                        "genus": "Faecalibacterium",
                        "direction": "down",
                        "p_value": 0.001,
                        "q_value": 0.01,
                        "log2fc": -1.5,
                    }
                ]
            },
            "taxonomy": {"S1": {"top_genera": ["Faecalibacterium", "Inventedium"]}},
        },
        "literature": {"entries": []},
    }
    uni = table_bound_universe(state)
    assert "Faecalibacterium" in uni["allowed_taxa"]
    assert assert_stats_from_table("Faecalibacterium", p_value=0.001, effect_size=-1.5, universe=uni)["ok"]
    assert assert_stats_from_table("Faecalibacterium", p_value=0.99, universe=uni)["ok"] is False
    assert assert_stats_from_table("Inventedium", p_value=0.01, universe=uni)["ok"] is False

    claim_ok = build_claim("Faecalibacterium", state, direction="down")
    assert claim_ok["allowed"] is True
    # Top-genus without table stats blocked when require_evidence_chain
    state2 = {
        **state,
        "artifacts": {
            "statistics": {"biomarker_list": []},
            "taxonomy": {"S1": {"top_genera": ["Faecalibacterium"]}},
        },
    }
    claim_block = build_claim("Faecalibacterium", state2)
    assert claim_block["allowed"] is False
    assert "table" in (claim_block["statement"] or "").lower() or "p_value" in (claim_block["statement"] or "")

    bundle = write_grounded_interp(state)
    assert bundle["n_allowed"] >= 1
    assert (tmp_path / "evidence" / "grounded_interp.md").exists()

    san = sanitize_interpretation_text(
        "Faecalibacterium decreased. Fakeobacter inventus increased.",
        uni,
    )
    assert "Faecalibacterium" in san["allowed_taxa_mentioned"]
    assert any("Fakeobacter" in s for s in san["ungrounded_name_suspects"])


def test_grounded_bundle_pcoa_note(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "config": {"interpretation": {"require_evidence_chain": True}},
        "artifacts": {"statistics": {"biomarker_list": []}},
    }
    b = grounded_interpretation_bundle(state)
    assert "PCoA" in (b.get("pcoa_note") or "") or "Beta" in (b.get("pcoa_note") or "")
