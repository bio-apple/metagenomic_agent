"""LangGraph multi-agent orchestration: Router → Specialists → Validator → Swarm → PI → XAI."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from metagenomic_agent.agents import bio_reasoning_agent
from metagenomic_agent.agents import (
    critic_agent,
    literature_agent,
    pi_agent,
    plan_validator,
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
from metagenomic_agent.execution.executor import execute_swarm
from metagenomic_agent.execution.workflow_params import write_workflow_params
from metagenomic_agent.execution.self_heal import (
    apply_self_heal,
    patch_workflow_params_on_heal,
    summarize_error_logs,
    classify_from_errors,
    deep_merge_config,
    summarize_heal_for_user,
)
from metagenomic_agent.input.parser import parse_input
from metagenomic_agent.report import generator as report_agent
from metagenomic_agent.skills.checker import contract_check
from metagenomic_agent.state import AgentState
from metagenomic_agent.validators.loop import validate
from metagenomic_agent.validators.recovery import apply_recovery, plan_recovery


def _route_after_hitl(state: AgentState) -> Literal["execute_swarm", "report"]:
    if state.get("error") or state.get("hitl_resolved") is False:
        return "report"
    return "execute_swarm"


def _route_after_validate(state: AgentState) -> Literal["self_heal", "critic"]:
    validation = state.get("validation") or {}
    errors = state.get("artifacts", {}).get("errors") or []
    if (not validation.get("passed")) or errors:
        if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
            return "self_heal"
    return "critic"


def _route_after_critic(state: AgentState) -> Literal["self_heal", "literature"]:
    critic = state.get("critic") or {}
    if critic.get("passed"):
        return "literature"
    if int(state.get("retry_count", 0)) < int(state.get("max_retries", 2)):
        recs = " ".join(critic.get("recommendations") or []).lower()
        if any(k in recs for k in ("metaphlan", "fastp", "quality", "assembler", "memory", "oom", "contract")):
            return "self_heal"
    return "literature"


def _route_after_pi(state: AgentState) -> Literal["self_heal", "visualization"]:
    if state.get("pi_replan"):
        return "self_heal"
    return "visualization"


def _self_heal(state: AgentState) -> dict:
    actions: list[str] = []
    errors = list(state.get("artifacts", {}).get("errors") or [])
    actions.extend(classify_from_errors(errors))
    validation = state.get("validation") or {}
    if validation and not validation.get("passed"):
        actions.extend(
            plan_recovery(state, validation.get("technical") or {}, validation.get("biological") or {})
        )
        actions.extend(validation.get("recovery_actions") or [])
    critic = state.get("critic") or {}
    recs = " ".join(critic.get("recommendations") or []).lower()
    if "metaphlan" in recs:
        actions.append("switch_taxonomy_tool")
    if "fastp" in recs or "quality" in recs:
        actions.append("loosen_qc")
    if "assembler" in recs or "megahit" in recs:
        actions.append("downgrade_assembler")
    if "glm" in recs or "microcafe" in recs or "long" in recs:
        actions.append("switch_taxonomy_tool")
    if state.get("pi_replan"):
        actions.append("switch_taxonomy_tool")
        actions.append("loosen_qc")

    actions = list(dict.fromkeys(actions))
    log_digest = summarize_error_logs(errors)
    new_dag, cfg_patch = apply_self_heal(list(state.get("dag", [])), actions, state.get("config"))
    new_dag = apply_recovery(new_dag, actions)
    new_config = deep_merge_config(dict(state.get("config") or {}), cfg_patch)
    artifacts = dict(state.get("artifacts") or {})
    artifacts["errors"] = []
    artifacts["self_heal_actions"] = actions
    artifacts["self_heal_error_digest"] = log_digest
    summary = summarize_heal_for_user(actions, errors)
    artifacts["self_heal_summary"] = summary

    # Rewrite engine params.yaml/json with healed resources (structured retry, not shell rewrite)
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
    return {
        "artifacts": arts,
        "hitl_pending": hitl,
        "messages": state.get("messages", [])
        + [
            f"Exported workflow DAG ({info.get('n_nodes')} nodes)",
            estimate.get("user_message") or "resource estimate written",
            f"Wrote engine params ({wf_params.get('params_yaml')})",
        ],
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
                "question": f"样本 {', '.join(high_host)} 宿主污染偏高（≥20%）。请选择：",
                "choices": [
                    {"key": "A", "label": "继续分析", "action": "continue"},
                    {"key": "B", "label": "加强宿主去除 / 重新 QC", "action": "strengthen_host"},
                    {"key": "C", "label": "标记删除高污染样本", "action": "drop_flagged_samples"},
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
    g.add_node("export_dag", _export_dag)
    g.add_node("workflow_agent", workflow_agent.run)
    g.add_node("contract_check", contract_check)
    g.add_node("hitl", hitl_checkpoint)
    g.add_node("execute_swarm", execute_swarm)
    g.add_node("validate", validate)
    g.add_node("quality_scores", _quality_scores)
    g.add_node("hitl_runtime", hitl_checkpoint)
    g.add_node("self_heal", _self_heal)
    g.add_node("critic", critic_agent.run)
    g.add_node("literature", literature_agent.run)
    g.add_node("pi_review", pi_agent.run)
    g.add_node("visualization", visualization_agent.run)
    g.add_node("xai", _xai)
    g.add_node("report", report_agent.run)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "router")
    g.add_edge("router", "bio_reasoning")
    g.add_edge("bio_reasoning", "supervisor")
    g.add_edge("supervisor", "tool_specialist")
    g.add_edge("tool_specialist", "plan_validator")
    g.add_edge("plan_validator", "export_dag")
    g.add_edge("export_dag", "workflow_agent")
    g.add_edge("workflow_agent", "contract_check")
    g.add_edge("contract_check", "hitl")
    g.add_conditional_edges("hitl", _route_after_hitl, {"execute_swarm": "execute_swarm", "report": "report"})
    g.add_edge("execute_swarm", "validate")
    g.add_edge("validate", "quality_scores")
    g.add_edge("quality_scores", "hitl_runtime")
    g.add_conditional_edges(
        "hitl_runtime", _route_after_validate, {"self_heal": "self_heal", "critic": "critic"}
    )
    g.add_edge("self_heal", "execute_swarm")
    g.add_conditional_edges("critic", _route_after_critic, {"self_heal": "self_heal", "literature": "literature"})
    g.add_edge("literature", "pi_review")
    g.add_conditional_edges(
        "pi_review", _route_after_pi, {"self_heal": "self_heal", "visualization": "visualization"}
    )
    g.add_edge("visualization", "xai")
    g.add_edge("xai", "report")
    g.add_edge("report", END)
    return g.compile()


def run_pipeline(initial: AgentState) -> AgentState:
    return build_graph().invoke(initial)
