"""Self-Heal FPR scenarios, policy filter, and HITL high-risk gate."""

from __future__ import annotations

from metagenomic_agent.agents.hitl_gates import build_self_heal_gate
from metagenomic_agent.evaluation.self_heal_fpr import catalog, evaluate_self_heal_fpr, score_scenario
from metagenomic_agent.execution.self_heal import (
    collect_heal_actions,
    critic_suggests_heal,
    filter_actions_for_policy,
)
from metagenomic_agent.graph import _route_after_critic, _route_after_self_heal, _self_heal


def test_critic_bare_quality_does_not_suggest_heal():
    assert not critic_suggests_heal(
        ["Overall sample quality looks acceptable; consider reporting gut marker coverage."]
    )
    assert critic_suggests_heal(["Re-run fastp with lower phred / Q30 thresholds."])


def test_self_heal_fpr_suite_trigger_and_policy():
    report = evaluate_self_heal_fpr()
    assert report["trigger"]["fpr"] == 0.0
    assert report["spot_checks"]["taxonomy_oom_no_assembler_downgrade"]
    # Forbidden actions may still be *proposed* (e.g. mock fallback) but must be withheld
    assert report["action"]["fpr_after_safe_policy"] == 0.0
    soft = next(r for r in report["scenarios"] if r["id"] == "soft_qc_warning")
    assert soft["false_trigger"] is False
    tax = next(r for r in report["scenarios"] if r["id"] == "oom_taxonomy")
    assert "downgrade_assembler" not in tax["proposed"]


def test_each_catalog_scenario_has_no_forbidden_after_policy():
    for s in catalog():
        row = score_scenario(s)
        assert row["fp_actions_after_safe_policy"] == [], row


def test_filter_withholds_high_risk():
    applied, withheld = filter_actions_for_policy(
        ["increase_memory", "loosen_qc", "switch_to_mock_fallback"],
        approve_high_risk=False,
    )
    assert applied == ["increase_memory"]
    assert set(withheld) == {"loosen_qc", "switch_to_mock_fallback"}


def test_build_self_heal_gate_only_when_high_risk():
    assert build_self_heal_gate({"config": {"hitl": {}}}, ["increase_memory"]) is None
    gate = build_self_heal_gate({"config": {"hitl": {}}}, ["loosen_qc", "increase_memory"])
    assert gate is not None
    assert gate["id"] == "confirm_self_heal"
    assert gate["default"] == "B"


def test_self_heal_node_safe_policy_default():
    state = {
        "dag": [
            {
                "id": "qc",
                "agent": "qc",
                "tools": ["fastp"],
                "params": {},
                "depends_on": [],
                "status": "failed",
            }
        ],
        "config": {"hitl": {"require_self_heal_confirm": True, "default_self_heal": "B", "auto_confirm": True}},
        "artifacts": {
            "errors": [],
        },
        "critic": {"passed": False, "recommendations": ["Re-run fastp with lower phred"]},
        "hitl_auto_confirm": True,
        "retry_count": 0,
        "messages": [],
        "validation": {"passed": True},
    }
    # collect would propose loosen_qc; auto default B withholds it → skip
    out = _self_heal(state)
    assert out["artifacts"]["self_heal_decision"] == "approve_safe_heal_only"
    assert "loosen_qc" in (out["artifacts"].get("self_heal_withheld") or out["artifacts"].get("self_heal_proposed"))
    assert out["artifacts"].get("self_heal_skipped") is True
    assert _route_after_self_heal(out) == "critic"


def test_self_heal_applies_safe_oom_actions():
    state = {
        "dag": [
            {
                "id": "taxonomy_profiling",
                "agent": "taxonomy",
                "tools": ["kraken2"],
                "params": {},
                "depends_on": [],
                "status": "failed",
            }
        ],
        "config": {
            "hitl": {"require_self_heal_confirm": True, "default_self_heal": "B", "auto_confirm": True},
            "linux": {"memory_gb": 32, "threads": 8},
            "docker": {"threads": 8},
        },
        "artifacts": {
            "errors": [
                {
                    "node": "taxonomy_profiling",
                    "agent": "taxonomy",
                    "classified": "oom",
                    "returncode": 137,
                }
            ]
        },
        "hitl_auto_confirm": True,
        "retry_count": 0,
        "messages": [],
        "validation": {"passed": False, "technical": {}, "biological": {"ok": True}},
    }
    proposed = collect_heal_actions(state)
    assert "increase_memory" in proposed
    assert "downgrade_assembler" not in proposed
    out = _self_heal(state)
    assert out["artifacts"]["self_heal_skipped"] is False
    assert "increase_memory" in out["artifacts"]["self_heal_actions"]
    assert out["config"]["linux"]["memory_gb"] == 64
    assert _route_after_self_heal(out) == "execute_swarm"


def test_route_after_critic_ignores_bare_quality():
    state = {
        "critic": {"passed": False, "recommendations": ["sample quality is fine"]},
        "retry_count": 0,
        "max_retries": 2,
    }
    assert _route_after_critic(state) == "literature"
