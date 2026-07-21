"""LangGraph multi-agent orchestration: Router → Specialists → Validator → Swarm → PI → XAI."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from metagenomic_agent.agents import bio_reasoning_agent
from metagenomic_agent.agents import (
    code_agent,
    critic_agent,
    evidence_agent,
    executor_agent,
    literature_agent,
    pi_agent,
    plan_validator,
    planner_agent,
    reflection_agent,
    reporter_agent,
    reviewer_agent,
    router_agent,
    supervisor,
    tool_specialist,
    visualization_agent,
    workflow_agent,
)
from metagenomic_agent.agents.hitl import hitl_checkpoint
from metagenomic_agent.evaluation.quality_score import write_quality_report
from metagenomic_agent.evaluation.xai import write_xai_report
from metagenomic_agent.execution.dag_export import export_workflow_dag
from metagenomic_agent.execution.resource_estimate import write_resource_estimate
from metagenomic_agent.execution.workflow_params import write_workflow_params
from metagenomic_agent.execution.self_heal import (
    apply_self_heal,
    collect_heal_actions,
    critic_suggests_heal,
    deep_merge_config,
    filter_actions_for_policy,
    partition_actions,
    patch_workflow_params_on_heal,
    summarize_error_logs,
    summarize_heal_for_user,
)
from metagenomic_agent.input.parser import parse_input
from metagenomic_agent.report import generator as report_agent
from metagenomic_agent.skills.checker import contract_check
from metagenomic_agent.state import AgentState
from metagenomic_agent.validators.loop import validate
from metagenomic_agent.validators.recovery import apply_recovery


def _route_after_hitl(state: AgentState) -> Literal["execute_swarm", "report", "awaiting"]:
    if state.get("hitl_awaiting"):
        return "awaiting"
    if state.get("error") or state.get("hitl_resolved") is False:
        return "report"
    return "execute_swarm"


def _awaiting_end(state: AgentState) -> dict:
    """Park pipeline for async HITL — no final report yet."""
    return {
        "messages": state.get("messages", []) + ["Pipeline paused: awaiting HITL API decisions"],
        "report_path": None,
    }


def _route_after_validate(state: AgentState) -> Literal["self_heal", "critic"]:
    validation = state.get("validation") or {}
    errors = state.get("artifacts", {}).get("errors") or []
    if (not validation.get("passed")) or errors:
        if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
            return "self_heal"
    return "critic"


def _route_after_critic(state: AgentState) -> Literal["scientific_replan", "self_heal", "literature"]:
    critic = state.get("critic") or {}
    if critic.get("passed"):
        return "literature"
    from metagenomic_agent.agents.scientific_replan import should_scientific_replan

    arts = state.get("artifacts") or {}
    replan_n = int(arts.get("scientific_replan_count") or 0)
    max_replan = int((state.get("config") or {}).get("pi", {}).get("max_replans", 1))
    if replan_n < max_replan and should_scientific_replan(state):
        return "scientific_replan"
    if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
        if critic_suggests_heal(critic.get("recommendations")):
            return "self_heal"
    return "literature"


def _route_after_pi(state: AgentState) -> Literal["scientific_replan", "self_heal", "visualization"]:
    if not state.get("pi_replan"):
        return "visualization"
    from metagenomic_agent.agents.scientific_replan import should_scientific_replan

    arts = state.get("artifacts") or {}
    replan_n = int(arts.get("scientific_replan_count") or 0)
    max_replan = int((state.get("config") or {}).get("pi", {}).get("max_replans", 1))
    if replan_n < max_replan and should_scientific_replan(state):
        return "scientific_replan"
    # Resource-level fallback when redesign budget exhausted
    if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
        return "self_heal"
    return "visualization"


def _scientific_replan(state: AgentState) -> dict:
    from metagenomic_agent.agents.scientific_replan import apply_scientific_replan

    return apply_scientific_replan(state)


def _route_after_self_heal(state: AgentState) -> Literal["execute_swarm", "critic"]:
    """If analyst rejects heal (or only audit), continue to critic instead of re-running swarm."""
    arts = state.get("artifacts") or {}
    if arts.get("self_heal_skipped"):
        return "critic"
    return "execute_swarm"


def _resolve_self_heal_policy(state: AgentState, proposed: list[str]) -> tuple[str, bool, list[str]]:
    """Return (decision, approve_high_risk, approved_action_list).

    decision ∈ approve_all_heal | approve_safe_heal_only | reject_heal
    """
    from metagenomic_agent.agents.hitl_gates import build_self_heal_gate, confirm_gate_inline

    hitl_cfg = (state.get("config") or {}).get("hitl") or {}
    arts = state.get("artifacts") or {}
    parts = partition_actions(proposed)
    prior = arts.get("self_heal_decision")
    if prior in {"approve_all_heal", "approve_safe_heal_only", "reject_heal"}:
        return (
            prior,
            prior == "approve_all_heal",
            list(arts.get("self_heal_approved_actions") or []),
        )

    require = bool(hitl_cfg.get("require_self_heal_confirm", True))
    if not parts["high"] or not require:
        # No high-risk → auto safe path; or policy disabled → apply all proposed
        if not require:
            return "approve_all_heal", True, list(proposed)
        return "approve_safe_heal_only", False, []

    auto = bool(state.get("hitl_auto_confirm")) or bool(hitl_cfg.get("auto_confirm", False))
    gate = build_self_heal_gate(state, proposed)
    if gate is None:
        return "approve_safe_heal_only", False, []

    async_mode = str(hitl_cfg.get("mode") or "").lower() == "async" or bool(state.get("hitl_async"))
    if async_mode and not auto:
        # Park: resume after /hitl/decide; until then withhold high-risk
        return "approve_safe_heal_only", False, []

    action, _patch = confirm_gate_inline(state, gate, auto=auto)
    if action == "approve_all_heal":
        return action, True, list(proposed)
    if action == "reject_heal":
        return action, False, []
    return "approve_safe_heal_only", False, []


def _self_heal(state: AgentState) -> dict:
    errors = list(state.get("artifacts", {}).get("errors") or [])
    proposed = collect_heal_actions(state)
    decision, approve_high, approved_list = _resolve_self_heal_policy(state, proposed)
    actions, withheld = filter_actions_for_policy(
        proposed, approve_high_risk=approve_high, approved_actions=approved_list
    )
    log_digest = summarize_error_logs(errors)
    artifacts = dict(state.get("artifacts") or {})
    artifacts["self_heal_proposed"] = proposed
    artifacts["self_heal_decision"] = decision
    artifacts["self_heal_withheld"] = withheld
    artifacts["self_heal_risk"] = partition_actions(proposed)
    artifacts["self_heal_error_digest"] = log_digest

    if decision == "reject_heal" or not actions:
        artifacts["self_heal_skipped"] = True
        artifacts["self_heal_actions"] = []
        summary = (
            f"Self-heal skipped (decision={decision}); withheld={withheld or proposed}"
            if decision == "reject_heal"
            else "Self-heal: no safe actions to apply"
        )
        artifacts["self_heal_summary"] = summary
        # Do not clear errors — critic / report must see the failure
        return {
            "artifacts": artifacts,
            "pi_replan": False,
            "messages": state.get("messages", []) + [summary],
        }

    new_dag, cfg_patch = apply_self_heal(list(state.get("dag", [])), actions, state.get("config"))
    new_dag = apply_recovery(new_dag, actions)
    new_config = deep_merge_config(dict(state.get("config") or {}), cfg_patch)
    artifacts["errors"] = []
    artifacts["self_heal_actions"] = actions
    artifacts["self_heal_skipped"] = False
    summary = summarize_heal_for_user(actions, errors)
    if withheld:
        summary += f"; deferred high-risk actions (HITL required): {', '.join(withheld)}"
    artifacts["self_heal_summary"] = summary

    healed_state = {**state, "dag": new_dag, "config": new_config, "artifacts": artifacts}
    try:
        from pathlib import Path
        import yaml

        prev = artifacts.get("workflow_params") or {}
        yml_path = prev.get("params_yaml")
        base_params: dict = {}
        if yml_path and Path(yml_path).exists():
            base_params = yaml.safe_load(Path(yml_path).read_text(encoding="utf-8")) or {}
        if base_params:
            patched = patch_workflow_params_on_heal(base_params, cfg_patch, actions)
            Path(yml_path).write_text(
                yaml.safe_dump(patched, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )
            js = prev.get("params_json")
            if js:
                import json

                Path(js).write_text(json.dumps(patched, indent=2, ensure_ascii=False), encoding="utf-8")
            artifacts["workflow_params_healed"] = True
        else:
            artifacts["workflow_params"] = write_workflow_params(healed_state)
    except Exception as exc:  # noqa: BLE001
        artifacts["workflow_params_heal_error"] = str(exc)

    # Register audit gate record for report (even when auto safe-only)
    from metagenomic_agent.agents.hitl_gates import build_self_heal_gate

    gate = build_self_heal_gate({**state, "artifacts": artifacts}, proposed)
    if gate:
        opts = list(artifacts.get("hitl_options") or [])
        if not any(o.get("id") == gate["id"] for o in opts):
            # Audit-only stamp when already resolved this cycle
            artifacts.setdefault("hitl_critical_gates", [])
            if "self_heal_high_risk" not in artifacts["hitl_critical_gates"]:
                artifacts["hitl_critical_gates"] = list(artifacts["hitl_critical_gates"]) + [
                    "self_heal_high_risk"
                ]

    return {
        "dag": new_dag,
        "config": new_config,
        "artifacts": artifacts,
        "pi_replan": False,
        "retry_count": int(state.get("retry_count", 0)) + 1,
        "messages": state.get("messages", [])
        + [summary, f"Self-heal retry={int(state.get('retry_count', 0)) + 1}"],
    }


def _export_dag(state: AgentState) -> dict:
    from metagenomic_agent.agents.hitl_gates import register_critical_gates

    info = export_workflow_dag(state)
    estimate = write_resource_estimate(state)
    # Agent → validated YAML/JSON params for Nextflow/Snakemake (no LLM shell)
    wf_params = write_workflow_params(state)
    arts = dict(state.get("artifacts") or {})
    arts["workflow_dag"] = info
    arts["resource_estimate"] = estimate
    arts["workflow_params"] = wf_params
    hitl = list(state.get("hitl_pending") or [])
    if estimate.get("warnings") and state.get("mode") not in {"mock"}:
        hitl.append(f"[Resources] {estimate.get('user_message')}")
    if int(wf_params.get("n_validation_errors") or 0) > 0 and state.get("mode") not in {"mock"}:
        hitl.append(f"[Schema] {wf_params['n_validation_errors']} tool param validation error(s)")
    # Critical HITL: Assembly compute + OTU/ASV prevalence thresholds
    gated = register_critical_gates(
        {**state, "artifacts": arts, "hitl_pending": hitl, "messages": state.get("messages") or []}
    )
    arts = gated.get("artifacts") or arts
    hitl = gated.get("hitl_pending") or hitl
    return {
        "artifacts": arts,
        "hitl_pending": hitl,
        "messages": state.get("messages", [])
        + [
            f"Exported workflow DAG ({info.get('n_nodes')} nodes)",
            estimate.get("user_message") or "resource estimate written",
            f"Wrote engine params ({wf_params.get('params_yaml')})",
        ]
        + list(gated.get("messages") or [])[-1:],
    }


def _quality_scores(state: AgentState) -> dict:
    from metagenomic_agent.coordinator.summary import write_pipeline_summary

    report = write_quality_report(state)
    arts = dict(state.get("artifacts") or {})
    arts["quality_scores"] = report
    summary_full = write_pipeline_summary({**state, "artifacts": arts})
    llm_ctx = summary_full.pop("_llm_context", "")
    arts["pipeline_summary"] = {k: v for k, v in summary_full.items() if not k.startswith("_")}
    arts["llm_context"] = llm_ctx

    # Multi-option HITL when host contamination is high
    qc = arts.get("qc_host") or {}
    high_host = [
        sid for sid, v in qc.items() if float(v.get("host_fraction") or 0) >= 0.2
    ]
    hitl_options = list(arts.get("hitl_options") or [])
    hitl_pending = list(state.get("hitl_pending") or [])
    if high_host and not any(o.get("id") == "host_contamination" for o in hitl_options):
        hitl_options.append(
            {
                "id": "host_contamination",
                "question": f"Samples {', '.join(high_host)} have elevated host contamination (≥20%). Choose an action:",
                "choices": [
                    {"key": "A", "label": "Continue analysis", "action": "continue"},
                    {"key": "B", "label": "Strengthen host removal / re-run QC", "action": "strengthen_host"},
                    {"key": "C", "label": "Flag and drop high-contamination samples", "action": "drop_flagged_samples"},
                ],
                "default": "A",
            }
        )
        hitl_pending.append(f"[QC] high host fraction in {high_host} — choose A/B/C")
        arts["hitl_options"] = hitl_options

    out: dict = {
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [
            f"Quality overall={report.get('scores', {}).get('Overall Score')}",
            "Refreshed pipeline_summary for LLM context",
        ],
    }
    if high_host:
        out["hitl_pending"] = hitl_pending
    return out


def _xai(state: AgentState) -> dict:
    report = write_xai_report(state)
    arts = dict(state.get("artifacts") or {})
    arts["xai"] = report
    return {
        "artifacts": arts,
        "messages": state.get("messages", []) + [f"XAI: {report.get('summary')}"],
    }


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("parse_input", parse_input)
    g.add_node("router", router_agent.run)
    g.add_node("bio_reasoning", bio_reasoning_agent.run)
    g.add_node("supervisor", supervisor.plan)
    g.add_node("tool_specialist", tool_specialist.run)
    g.add_node("plan_validator", plan_validator.run)
    g.add_node("planner", planner_agent.run)
    g.add_node("export_dag", _export_dag)
    g.add_node("workflow_agent", workflow_agent.run)
    g.add_node("contract_check", contract_check)
    g.add_node("hitl", hitl_checkpoint)
    g.add_node("awaiting_hitl", _awaiting_end)
    # Executor wraps swarm + HPC/K8s specs (role: Executor/Bioinfo)
    g.add_node("execute_swarm", executor_agent.run)
    g.add_node("validate", validate)
    g.add_node("quality_scores", _quality_scores)
    g.add_node("hitl_runtime", hitl_checkpoint)
    g.add_node("self_heal", _self_heal)
    g.add_node("scientific_replan", _scientific_replan)
    g.add_node("critic", critic_agent.run)  # QC & Critic
    g.add_node("literature", literature_agent.run)
    g.add_node("evidence", evidence_agent.run)
    g.add_node("reviewer", reviewer_agent.run)
    g.add_node("reflection", reflection_agent.run)
    g.add_node("pi_review", pi_agent.run)
    g.add_node("visualization", visualization_agent.run)
    g.add_node("code_agent", code_agent.run)
    g.add_node("reporter", reporter_agent.run)
    g.add_node("xai", _xai)
    g.add_node("report", report_agent.run)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "router")
    g.add_edge("router", "bio_reasoning")
    g.add_edge("bio_reasoning", "supervisor")
    g.add_edge("supervisor", "tool_specialist")
    g.add_edge("tool_specialist", "plan_validator")
    g.add_edge("plan_validator", "planner")
    g.add_edge("planner", "export_dag")
    g.add_edge("export_dag", "workflow_agent")
    g.add_edge("workflow_agent", "contract_check")
    g.add_edge("contract_check", "hitl")
    g.add_conditional_edges(
        "hitl",
        _route_after_hitl,
        {"execute_swarm": "execute_swarm", "report": "report", "awaiting": "awaiting_hitl"},
    )
    g.add_edge("awaiting_hitl", END)
    g.add_edge("execute_swarm", "validate")
    g.add_edge("validate", "quality_scores")
    g.add_edge("quality_scores", "hitl_runtime")
    g.add_conditional_edges(
        "hitl_runtime", _route_after_validate, {"self_heal": "self_heal", "critic": "critic"}
    )
    g.add_conditional_edges(
        "self_heal",
        _route_after_self_heal,
        {"execute_swarm": "execute_swarm", "critic": "critic"},
    )
    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "scientific_replan": "scientific_replan",
            "self_heal": "self_heal",
            "literature": "literature",
        },
    )
    g.add_edge("scientific_replan", "execute_swarm")
    g.add_edge("literature", "evidence")
    g.add_edge("evidence", "reviewer")
    g.add_edge("reviewer", "reflection")
    g.add_edge("reflection", "pi_review")
    g.add_conditional_edges(
        "pi_review",
        _route_after_pi,
        {
            "scientific_replan": "scientific_replan",
            "self_heal": "self_heal",
            "visualization": "visualization",
        },
    )
    g.add_edge("visualization", "code_agent")
    g.add_edge("code_agent", "reporter")
    g.add_edge("reporter", "xai")
    g.add_edge("xai", "report")
    g.add_edge("report", END)
    return g.compile()


def build_resume_graph():
    """Tail graph after async HITL decisions — starts at execute_swarm."""
    g = StateGraph(AgentState)
    g.add_node("execute_swarm", executor_agent.run)
    g.add_node("validate", validate)
    g.add_node("quality_scores", _quality_scores)
    g.add_node("hitl_runtime", hitl_checkpoint)
    g.add_node("self_heal", _self_heal)
    g.add_node("scientific_replan", _scientific_replan)
    g.add_node("critic", critic_agent.run)
    g.add_node("literature", literature_agent.run)
    g.add_node("evidence", evidence_agent.run)
    g.add_node("reviewer", reviewer_agent.run)
    g.add_node("reflection", reflection_agent.run)
    g.add_node("pi_review", pi_agent.run)
    g.add_node("visualization", visualization_agent.run)
    g.add_node("code_agent", code_agent.run)
    g.add_node("reporter", reporter_agent.run)
    g.add_node("xai", _xai)
    g.add_node("report", report_agent.run)
    g.set_entry_point("execute_swarm")
    g.add_edge("execute_swarm", "validate")
    g.add_edge("validate", "quality_scores")
    g.add_edge("quality_scores", "hitl_runtime")
    g.add_conditional_edges(
        "hitl_runtime", _route_after_validate, {"self_heal": "self_heal", "critic": "critic"}
    )
    g.add_conditional_edges(
        "self_heal",
        _route_after_self_heal,
        {"execute_swarm": "execute_swarm", "critic": "critic"},
    )
    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "scientific_replan": "scientific_replan",
            "self_heal": "self_heal",
            "literature": "literature",
        },
    )
    g.add_edge("scientific_replan", "execute_swarm")
    g.add_edge("literature", "evidence")
    g.add_edge("evidence", "reviewer")
    g.add_edge("reviewer", "reflection")
    g.add_edge("reflection", "pi_review")
    g.add_conditional_edges(
        "pi_review",
        _route_after_pi,
        {
            "scientific_replan": "scientific_replan",
            "self_heal": "self_heal",
            "visualization": "visualization",
        },
    )
    g.add_edge("visualization", "code_agent")
    g.add_edge("code_agent", "reporter")
    g.add_edge("reporter", "xai")
    g.add_edge("xai", "report")
    g.add_edge("report", END)
    return g.compile()


def run_pipeline(initial: AgentState) -> AgentState:
    return build_graph().invoke(initial)


def resume_pipeline(state: AgentState) -> AgentState:
    """Continue after async HITL approval."""
    return build_resume_graph().invoke(state)
