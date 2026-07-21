"""Self-Heal false-positive evaluation (action-level + trigger-level).

Definitions used in docs/SELF_HEAL.md:

* **False positive trigger**: heal route would fire when gold says do not heal.
* **False positive action**: proposed action is in the scenario's ``forbidden`` set
  (inappropriate correction that can change biology or fabricate success).
* **True positive action**: proposed ∩ allowed (non-empty for positive scenarios).

Run::

    python -c "from metagenomic_agent.evaluation.self_heal_fpr import evaluate_self_heal_fpr; \
               import json; print(json.dumps(evaluate_self_heal_fpr(), indent=2))"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from metagenomic_agent.execution.self_heal import (
    HIGH_RISK_ACTIONS,
    classify_from_errors,
    collect_heal_actions,
    critic_suggests_heal,
    filter_actions_for_policy,
)


@dataclass
class HealScenario:
    id: str
    title: str
    should_heal: bool
    allowed: set[str] = field(default_factory=set)
    forbidden: set[str] = field(default_factory=set)
    errors: list[dict[str, Any]] = field(default_factory=list)
    validation: dict[str, Any] | None = None
    critic_recommendations: list[str] | None = None
    pi_replan: bool = False
    notes: str = ""


def catalog() -> list[HealScenario]:
    """Curated mis-heal / correct-heal scenarios for FPR regression."""
    return [
        HealScenario(
            id="oom_assembly",
            title="metaSPAdes OOM on assembly node",
            should_heal=True,
            allowed={"increase_memory", "reduce_threads", "downgrade_assembler"},
            forbidden={"loosen_qc", "switch_to_mock_fallback", "lower_kraken_confidence"},
            errors=[
                {
                    "node": "assembly_binning",
                    "agent": "assembly",
                    "classified": "oom",
                    "returncode": 137,
                    "error": "Killed",
                }
            ],
            notes="Assembly OOM may legitimately downgrade to MEGAHIT.",
        ),
        HealScenario(
            id="oom_taxonomy",
            title="Kraken2 OOM — must NOT downgrade assembler",
            should_heal=True,
            allowed={"increase_memory", "reduce_threads"},
            forbidden={"downgrade_assembler", "loosen_qc", "switch_to_mock_fallback"},
            errors=[
                {
                    "node": "taxonomy_profiling",
                    "agent": "taxonomy",
                    "tool": "kraken2",
                    "classified": "oom",
                    "returncode": 137,
                    "stderr": "cannot allocate memory",
                }
            ],
            notes="Classic false correction before node-scoping.",
        ),
        HealScenario(
            id="soft_qc_warning",
            title="Critic soft warning with bare quality — should NOT trigger heal",
            should_heal=False,
            allowed=set(),
            forbidden={"loosen_qc", "downgrade_assembler", "switch_to_mock_fallback"},
            critic_recommendations=[
                "Overall sample quality looks acceptable; consider reporting gut marker coverage."
            ],
            notes="Keyword quality previously false-triggered loosen_qc.",
        ),
        HealScenario(
            id="fastp_phred_real",
            title="Critic recommends fastp / Q30 — loosen_qc high-risk but may be proposed",
            should_heal=True,
            allowed={"loosen_qc"},
            forbidden={"downgrade_assembler", "switch_to_mock_fallback"},
            critic_recommendations=["Re-run fastp with lower phred / Q30 thresholds."],
            notes="Proposed OK; default HITL policy withholds until analyst approves.",
        ),
        HealScenario(
            id="missing_db",
            title="Missing Kraken DB — fix path / add MetaPhlAn, not mock",
            should_heal=True,
            allowed={"fix_db_path", "switch_taxonomy_tool"},
            forbidden={"switch_to_mock_fallback", "loosen_qc", "downgrade_assembler"},
            errors=[
                {
                    "classified": "missing_db",
                    "stderr": "hash.k2d not found in database",
                    "node": "taxonomy_profiling",
                }
            ],
        ),
        HealScenario(
            id="missing_binary",
            title="Missing binary — container OK; mock is high-risk if auto-applied",
            should_heal=True,
            allowed={"switch_to_container", "switch_to_mock_fallback"},
            forbidden={"loosen_qc", "lower_kraken_confidence", "downgrade_assembler"},
            errors=[{"classified": "missing_binary", "stderr": "kraken2: command not found"}],
            notes="mock fallback allowed as last resort but must be HITL-gated.",
        ),
        HealScenario(
            id="bio_fail_confidence",
            title="Biological validation fail → lower_kraken_confidence (high risk)",
            should_heal=True,
            allowed={"lower_kraken_confidence", "retry_failed_nodes"},
            forbidden={"switch_to_mock_fallback", "downgrade_assembler"},
            validation={
                "passed": False,
                "technical": {"samples": {}},
                "biological": {"ok": False, "reason": "unexpected taxa for gut niche"},
            },
            notes="May mask contamination; HITL must gate.",
        ),
        HealScenario(
            id="pi_replan",
            title="PI replan should not force loosen_qc",
            should_heal=True,
            allowed={"switch_taxonomy_tool"},
            forbidden={"loosen_qc", "downgrade_assembler", "switch_to_mock_fallback"},
            pi_replan=True,
        ),
        HealScenario(
            id="killed_non_oom_logic",
            title="Generic logic failure — no assembler/QC silent downgrade",
            should_heal=True,
            allowed={"switch_taxonomy_tool"},
            forbidden={"downgrade_assembler", "loosen_qc", "switch_to_mock_fallback"},
            errors=[{"classified": "logic", "stderr": "unexpected exit", "node": "taxonomy"}],
        ),
    ]


def _state_from_scenario(s: HealScenario) -> dict[str, Any]:
    arts: dict[str, Any] = {"errors": list(s.errors)}
    st: dict[str, Any] = {
        "artifacts": arts,
        "config": {},
        "pi_replan": s.pi_replan,
    }
    if s.validation is not None:
        st["validation"] = s.validation
    if s.critic_recommendations is not None:
        st["critic"] = {"passed": False, "recommendations": list(s.critic_recommendations)}
    return st


def score_scenario(s: HealScenario) -> dict[str, Any]:
    state = _state_from_scenario(s)
    proposed = collect_heal_actions(state)
    trigger = bool(s.errors) or (
        s.validation is not None and not s.validation.get("passed", True)
    )
    if s.critic_recommendations is not None and not s.errors:
        trigger = critic_suggests_heal(s.critic_recommendations)
    if s.pi_replan:
        trigger = True

    fp_actions = sorted(set(proposed) & s.forbidden)
    tp_actions = sorted(set(proposed) & s.allowed)
    unexpected = sorted(set(proposed) - s.allowed - s.forbidden)

    applied, withheld = filter_actions_for_policy(proposed, approve_high_risk=False)
    fp_after_policy = sorted(set(applied) & s.forbidden)

    false_trigger = bool(trigger and not s.should_heal)
    missed_trigger = bool((not trigger) and s.should_heal)

    passed = (not false_trigger) and (not fp_actions) and (not missed_trigger)

    return {
        "id": s.id,
        "title": s.title,
        "notes": s.notes,
        "should_heal": s.should_heal,
        "trigger": trigger,
        "false_trigger": false_trigger,
        "missed_trigger": missed_trigger,
        "proposed": proposed,
        "tp_actions": tp_actions,
        "fp_actions": fp_actions,
        "unexpected_actions": unexpected,
        "applied_safe_policy": applied,
        "withheld_high_risk": withheld,
        "fp_actions_after_safe_policy": fp_after_policy,
        "high_risk_in_proposed": sorted(set(proposed) & set(HIGH_RISK_ACTIONS)),
        "passed": passed,
    }


def evaluate_self_heal_fpr(*, write_dir: Path | None = None) -> dict[str, Any]:
    rows = [score_scenario(s) for s in catalog()]
    n = len(rows)
    neg = [r for r in rows if not r["should_heal"]]
    pos = [r for r in rows if r["should_heal"]]
    fp_trig = sum(1 for r in neg if r["false_trigger"])
    tn_trig = sum(1 for r in neg if not r["trigger"])
    tp_trig = sum(1 for r in pos if r["trigger"])
    fn_trig = sum(1 for r in pos if not r["trigger"])
    fpr_trigger = fp_trig / max(1, fp_trig + tn_trig)

    scen_with_fp_action = sum(1 for r in rows if r["fp_actions"])
    action_fpr = scen_with_fp_action / max(1, n)
    scen_fp_after = sum(1 for r in rows if r["fp_actions_after_safe_policy"])
    action_fpr_after_policy = scen_fp_after / max(1, n)

    report = {
        "n_scenarios": n,
        "trigger": {
            "tp": tp_trig,
            "fp": fp_trig,
            "tn": tn_trig,
            "fn": fn_trig,
            "fpr": round(fpr_trigger, 4),
            "definition": "P(heal triggered | gold should_heal=False)",
        },
        "action": {
            "scenarios_with_forbidden_proposed": scen_with_fp_action,
            "fpr": round(action_fpr, 4),
            "definition": "P(scenario proposes >=1 forbidden action)",
            "scenarios_with_forbidden_after_safe_policy": scen_fp_after,
            "fpr_after_safe_policy": round(action_fpr_after_policy, 4),
            "definition_after_policy": (
                "Same after filter_actions_for_policy(approve_high_risk=False); "
                "high-risk forbidden actions should be withheld"
            ),
        },
        "scenarios": rows,
        "policy": {
            "high_risk_actions": sorted(HIGH_RISK_ACTIONS),
            "default": "hitl.require_self_heal_confirm=true, default_self_heal=B (safe only)",
        },
    }

    tax_oom = classify_from_errors(
        [{"node": "taxonomy", "classified": "oom", "returncode": 137, "stderr": "OOM"}]
    )
    report["spot_checks"] = {
        "taxonomy_oom_actions": tax_oom,
        "taxonomy_oom_no_assembler_downgrade": "downgrade_assembler" not in tax_oom,
    }

    if write_dir is not None:
        write_dir = Path(write_dir)
        write_dir.mkdir(parents=True, exist_ok=True)
        (write_dir / "self_heal_fpr.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        lines = [
            "# Self-Heal FPR evaluation",
            "",
            f"- Trigger FPR: **{report['trigger']['fpr']}** (FP={fp_trig}, TN={tn_trig})",
            f"- Action FPR (forbidden proposed): **{report['action']['fpr']}**",
            f"- Action FPR after safe HITL policy: **{report['action']['fpr_after_safe_policy']}**",
            "",
            "| id | trigger | FP actions | after policy | pass |",
            "|----|---------|------------|--------------|------|",
        ]
        for r in rows:
            lines.append(
                f"| `{r['id']}` | {r['trigger']} | {r['fp_actions'] or '—'} | "
                f"{r['fp_actions_after_safe_policy'] or '—'} | {r['passed']} |"
            )
        (write_dir / "self_heal_fpr.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        report["paths"] = {
            "json": str(write_dir / "self_heal_fpr.json"),
            "md": str(write_dir / "self_heal_fpr.md"),
        }
    return report
