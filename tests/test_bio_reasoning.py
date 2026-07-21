"""Bio Reasoning Layer + HITL multi-option tests."""

from __future__ import annotations

from pathlib import Path

from metagenomic_agent.agents.bio_reasoning_agent import reason, run as bio_run
from metagenomic_agent.agents.hitl import _apply_action, hitl_checkpoint
from metagenomic_agent.agents.supervisor import _default_plan


def test_reason_obesity_shotgun():
    bio = reason("分析肥胖患者肠道菌群变化")
    assert bio["study_goal"] == "disease_association_differential"
    assert bio["disease_context"] == "obesity"
    assert bio["recommended_assay"] == "shotgun_metagenomics"
    assert bio["enable_host_filter"] is True
    assert bio["enable_function"] is True
    assert bio["enable_statistics"] is True
    assert "Taxonomic profiling" in bio["pipeline_steps"]
    assert bio["assembler_preference"] == "megahit"
    assert bio["expected_markers"]


def test_bio_run_writes_artifacts(tmp_path: Path):
    state = {
        "user_query": "IBD gut microbiome biomarker discovery",
        "outdir": str(tmp_path),
        "samples": [{"sample_id": "S1", "read_length_est": 150}],
        "artifacts": {"router": {"primary_intent": "biomarker_discovery", "domains": ["human_gut"]}},
        "messages": [],
        "hitl_pending": [],
    }
    out = bio_run(state)
    assert (tmp_path / "bio_reasoning.json").exists()
    assert (tmp_path / "bio_reasoning.md").exists()
    assert out["artifacts"]["bio_reasoning"]["disease_context"] == "IBD"
    assert out["artifacts"]["hitl_options"]
    assert any("BioReasoning" in x for x in out["hitl_pending"])


def test_supervisor_plan_uses_bio():
    bio = reason("肥胖患者肠道菌群变化与功能通路")
    tasks = _default_plan("肥胖患者肠道菌群变化与功能通路", {"pipeline": {}}, bio=bio)
    agents = {_normalize_wait(t["agent"]) for t in tasks}
    assert "qc" in agents or any("QC" in t["agent"] for t in tasks)
    assert any("Function" in t["agent"] or t["agent"] == "function" for t in tasks)
    assert any("Statistics" in t["agent"] or t["agent"] == "statistics" for t in tasks)


def _normalize_wait(name: str) -> str:
    return name.strip().lower().replace(" agent", "")


def test_hitl_auto_accept_plan():
    state = {
        "hitl_pending": ["note"],
        "hitl_auto_confirm": True,
        "config": {"pipeline": {}},
        "dag": [
            {"id": "quality_control", "agent": "qc", "tools": [], "params": {}, "depends_on": [], "status": "pending"},
            {"id": "functional_annotation", "agent": "functional", "tools": [], "params": {}, "depends_on": [], "status": "pending"},
        ],
        "artifacts": {
            "bio_reasoning": {"enable_function": True},
            "hitl_options": [
                {
                    "id": "study_design",
                    "question": "confirm?",
                    "choices": [
                        {"key": "A", "label": "ok", "action": "accept_plan"},
                        {"key": "B", "label": "tax only", "action": "taxonomy_only"},
                    ],
                    "default": "B",
                }
            ],
        },
        "messages": [],
        "agent_messages": [],
    }
    out = hitl_checkpoint(state)
    assert out["hitl_resolved"] is True
    assert out["config"]["pipeline"]["enable_functional"] is False
    agents = {n["agent"] for n in out["dag"]}
    assert "functional" not in agents


def test_apply_force_assembly():
    state = {
        "config": {"pipeline": {}},
        "dag": [{"id": "quality_control", "agent": "qc", "tools": [], "params": {}, "depends_on": []}],
        "artifacts": {"bio_reasoning": {"assembler_preference": "megahit"}},
        "messages": [],
    }
    out = _apply_action(state, "force_assembly")
    assert out["config"]["pipeline"]["enable_assembly"] is True
    assert any(n["agent"] == "assembly" for n in out["dag"])
