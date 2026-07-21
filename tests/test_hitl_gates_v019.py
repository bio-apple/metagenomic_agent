"""Critical HITL gates — assembly compute & OTU/ASV filters (v0.19)."""

from pathlib import Path

from metagenomic_agent.agents.hitl import _apply_action, hitl_checkpoint
from metagenomic_agent.agents.hitl_gates import (
    OTU_THRESHOLD_PRESETS,
    apply_otu_preset,
    build_assembly_gate,
    build_otu_filter_gate,
    register_critical_gates,
)
from metagenomic_agent.agents.statistics_agent import _filter_low_frequency


def test_build_assembly_gate_when_planned():
    state = {
        "samples": [{"sample_id": "S1"}, {"sample_id": "S2"}],
        "dag": [{"id": "assembly_binning", "agent": "assembly", "status": "pending", "tools": ["megahit"]}],
        "config": {"hitl": {"require_assembly_confirm": True}, "linux": {"threads": 16, "memory_gb": 64}},
        "artifacts": {
            "bio_reasoning": {"enable_assembly": True, "assembler_preference": "megahit"},
            "resource_estimate": {"stages": [{"agent": "assembly", "est_wall_hours": 4.0, "est_mem_gb": 64}]},
        },
    }
    gate = build_assembly_gate(state)
    assert gate is not None
    assert gate["id"] == "confirm_assembly"
    assert gate["critical"] is True
    assert any(c["action"] == "skip_assembly" for c in gate["choices"])


def test_build_otu_gate():
    state = {
        "dag": [{"id": "statistics", "agent": "statistics", "status": "pending"}],
        "config": {"hitl": {"require_otu_filter_confirm": True}, "statistics": {"min_prevalence": 0.1}},
        "artifacts": {"bio_reasoning": {"enable_statistics": True}},
    }
    gate = build_otu_filter_gate(state)
    assert gate is not None
    assert gate["id"] == "confirm_otu_asv_filter"
    assert len(gate["choices"]) == 4


def test_register_and_auto_hitl(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "hitl_pending": [],
        "hitl_auto_confirm": True,
        "samples": [{"sample_id": "S1"}],
        "dag": [
            {"id": "assembly_binning", "agent": "assembly", "status": "pending", "tools": ["megahit"], "params": {}},
            {"id": "statistics", "agent": "statistics", "status": "pending", "tools": [], "params": {}},
        ],
        "config": {
            "hitl": {"require_assembly_confirm": True, "require_otu_filter_confirm": True, "default_otu_filter": "B"},
            "pipeline": {},
            "statistics": {},
            "linux": {"threads": 8, "memory_gb": 32},
        },
        "artifacts": {
            "bio_reasoning": {"enable_assembly": True, "enable_statistics": True, "assembler_preference": "megahit"},
            "resource_estimate": {"stages": [{"agent": "assembly", "est_wall_hours": 2.0, "est_mem_gb": 32}]},
            "hitl_options": [],
        },
        "messages": [],
        "agent_messages": [],
    }
    gated = register_critical_gates(state)
    ids = {o["id"] for o in gated["artifacts"]["hitl_options"]}
    assert "confirm_assembly" in ids
    assert "confirm_otu_asv_filter" in ids

    out = hitl_checkpoint({**state, **gated, "artifacts": gated["artifacts"]})
    assert out["hitl_resolved"] is True
    assert out["artifacts"].get("assembly_confirmed") is True
    # default_otu_filter B = strict
    assert out["config"]["statistics"]["otu_filter_preset"] == "strict"
    assert out["config"]["statistics"]["min_prevalence"] == OTU_THRESHOLD_PRESETS["strict"]["min_prevalence"]
    assert (tmp_path / "hitl" / "critical_gates.json").exists()


def test_skip_assembly_action():
    state = {
        "config": {"pipeline": {"enable_assembly": True}},
        "dag": [
            {
                "id": "assembly_binning",
                "agent": "assembly",
                "status": "pending",
                "tools": ["megahit"],
                "params": {},
                "depends_on": [],
            }
        ],
        "artifacts": {"bio_reasoning": {"enable_assembly": True}},
        "messages": [],
    }
    out = _apply_action(state, "skip_assembly")
    assert out["artifacts"]["assembly_confirmed"] is False
    assert out["dag"][0]["status"] == "skipped"
    assert out["config"]["pipeline"]["enable_assembly"] is False


def test_otu_filter_removes_rare_taxa():
    matrix = {
        "S1": {"Common": 0.5, "Rare": 1e-9},
        "S2": {"Common": 0.4, "Rare": 0.0},
        "S3": {"Common": 0.6, "Rare": 0.0},
    }
    filtered, meta = _filter_low_frequency(matrix, min_prevalence=0.5, min_rel_abundance=1e-4)
    assert "Common" in filtered["S1"]
    assert "Rare" not in filtered["S1"]
    assert meta["n_removed"] >= 1


def test_apply_otu_preset():
    cfg = apply_otu_preset({}, "lenient")
    assert cfg["statistics"]["min_prevalence"] == 0.05
