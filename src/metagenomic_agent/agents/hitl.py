"""HITL checkpoint — multi-option decisions (A/B/C) + legacy confirm."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt

from metagenomic_agent.messaging import append_msg, emit
from metagenomic_agent.state import AgentState

console = Console()


def _apply_action(state: AgentState, action: str) -> dict[str, Any]:
    """Translate HITL choice into config / dag patches."""
    cfg = dict(state.get("config") or {})
    dag = list(state.get("dag") or [])
    arts = dict(state.get("artifacts") or {})
    bio = dict(arts.get("bio_reasoning") or {})
    messages: list[str] = []

    if action == "accept_plan":
        messages.append("HITL: accepted bio-reasoning plan")
    elif action == "taxonomy_only":
        bio["enable_function"] = False
        bio["enable_statistics"] = False
        bio["study_goal"] = "taxonomy_only"
        dag = [n for n in dag if n.get("agent") not in {"functional", "function", "statistics", "stats"}]
        for n in dag:
            if n.get("id") == "functional_annotation" or n.get("agent") in {"functional", "statistics"}:
                n["status"] = "skipped"
        cfg.setdefault("pipeline", {})["enable_functional"] = False
        cfg.setdefault("pipeline", {})["enable_statistics"] = False
        messages.append("HITL: taxonomy-only mode — skipped function/statistics nodes")
    elif action == "force_assembly":
        bio["enable_assembly"] = True
        cfg.setdefault("pipeline", {})["enable_assembly"] = True
        if not any(n.get("agent") == "assembly" for n in dag):
            dag.append(
                {
                    "id": "assembly_binning",
                    "agent": "assembly",
                    "tools": ["megahit", "metabat2", "checkm2"],
                    "params": {"assembler": bio.get("assembler_preference") or "megahit"},
                    "depends_on": ["quality_control"] if any(n.get("id") == "quality_control" for n in dag) else [],
                    "status": "pending",
                }
            )
        messages.append("HITL: forced MAG assembly onto DAG")
    elif action == "demo_mode":
        cfg.setdefault("statistics", {})["demo_mode"] = True
        messages.append("HITL: statistics.demo_mode=true")
    elif action == "skip_stats":
        dag = [n for n in dag if n.get("agent") not in {"statistics", "stats"}]
        cfg.setdefault("pipeline", {})["enable_statistics"] = False
        messages.append("HITL: skipped statistics")
    elif action == "abort_for_metadata":
        return {
            "hitl_resolved": False,
            "error": "Aborted at HITL: provide --metadata with sample groups",
            "messages": state.get("messages", []) + ["HITL: abort for metadata"],
            "dag": [],
        }
    elif action == "continue":
        messages.append("HITL: continue despite warning")
    elif action == "strengthen_host":
        cfg.setdefault("pipeline", {})["enable_host_filter"] = True
        messages.append("HITL: strengthen host filtering")
    elif action == "drop_flagged_samples":
        arts["drop_samples_requested"] = True
        messages.append("HITL: user requested dropping flagged samples (recorded)")
    elif action == "re_qc":
        arts["re_qc_requested"] = True
        messages.append("HITL: re-QC requested")
    elif action == "confirm_assembly":
        bio["enable_assembly"] = True
        cfg.setdefault("pipeline", {})["enable_assembly"] = True
        arts["assembly_confirmed"] = True
        for n in dag:
            if n.get("agent") == "assembly":
                n["status"] = "pending"
                n.setdefault("params", {})["hitl_confirmed"] = True
        messages.append("HITL: Assembly compute confirmed by analyst")
    elif action == "confirm_assembly_megahit":
        bio["enable_assembly"] = True
        bio["assembler_preference"] = "megahit"
        cfg.setdefault("pipeline", {})["enable_assembly"] = True
        cfg.setdefault("pipeline", {})["default_assembler"] = "megahit"
        arts["assembly_confirmed"] = True
        for n in dag:
            if n.get("agent") == "assembly":
                n["status"] = "pending"
                n.setdefault("params", {})["assembler"] = "megahit"
                n["params"]["hitl_confirmed"] = True
                tools = [t for t in (n.get("tools") or []) if t != "metaspades"]
                if "megahit" not in tools:
                    tools.insert(0, "megahit")
                n["tools"] = tools
        messages.append("HITL: Assembly confirmed with MEGAHIT (memory-efficient)")
    elif action == "skip_assembly":
        bio["enable_assembly"] = False
        cfg.setdefault("pipeline", {})["enable_assembly"] = False
        arts["assembly_confirmed"] = False
        for n in dag:
            if n.get("agent") == "assembly":
                n["status"] = "skipped"
                n.setdefault("params", {})["hitl_skipped"] = True
        messages.append("HITL: Assembly skipped — analyst declined heavy compute")
    elif action in {
        "otu_filter_balanced",
        "otu_filter_strict",
        "otu_filter_lenient",
        "otu_filter_none",
    }:
        from metagenomic_agent.agents.hitl_gates import apply_otu_preset

        preset = action.replace("otu_filter_", "")
        cfg = apply_otu_preset(cfg, preset)
        arts["otu_filter_confirmed"] = True
        arts["otu_filter_preset"] = preset
        messages.append(
            f"HITL: OTU/ASV filter preset=`{preset}` "
            f"(prevalence≥{cfg['statistics']['min_prevalence']}, "
            f"rel_ab≥{cfg['statistics']['min_rel_abundance']})"
        )
    elif action == "confirm_databases":
        arts["databases_confirmed"] = True
        messages.append("HITL: reference databases confirmed ready")
    elif action == "databases_partial":
        arts["databases_confirmed"] = True
        arts["databases_partial"] = True
        messages.append("HITL: proceed with partial databases; missing-DB steps may self-heal/skip")
    elif action == "abort_for_databases":
        return {
            "hitl_resolved": False,
            "error": "Aborted at HITL: configure/download paths.kraken2_db|gtdb|host_index first",
            "messages": state.get("messages", []) + ["HITL: abort for databases"],
            "dag": [],
        }
    elif action == "publish_report":
        arts["report_publish_confirmed"] = True
        arts["report_shareable"] = True
        cfg.setdefault("report", {})["shareable"] = True
        messages.append("HITL: final report marked shareable / publishable")
    elif action == "draft_report_only":
        arts["report_publish_confirmed"] = True
        arts["report_shareable"] = False
        cfg.setdefault("report", {})["shareable"] = False
        messages.append("HITL: internal draft report only (not marked for external share)")
    elif action == "hold_report":
        arts["report_publish_confirmed"] = False
        arts["hold_report"] = True
        messages.append("HITL: report generation held — analyst deferred publish")

    arts["bio_reasoning"] = bio
    arts.setdefault("hitl_decisions", []).append(action)
    return {
        "config": cfg,
        "dag": dag,
        "artifacts": arts,
        "messages": messages,
        "hitl_resolved": True,
    }


def hitl_checkpoint(state: AgentState) -> dict[str, Any]:
    pending = list(state.get("hitl_pending") or [])
    options = list((state.get("artifacts") or {}).get("hitl_options") or [])
    auto = bool(state.get("hitl_auto_confirm"))
    hitl_cfg = (state.get("config") or {}).get("hitl") or {}
    async_mode = str(hitl_cfg.get("mode") or "").lower() == "async" or bool(state.get("hitl_async"))

    if not pending and not options:
        return {"hitl_resolved": True, "hitl_pending": [], "hitl_awaiting": False}

    # Async API/Web: park session for external approval (no Rich prompt)
    if async_mode and not auto and (options or pending):
        from metagenomic_agent.agents.hitl_async import write_awaiting_session

        session = write_awaiting_session(state)
        msg = emit("hitl", "api", "hitl", {"action": "awaiting", "run_id": state.get("run_id")})
        n_gates = len(options) or len(pending)
        return {
            "hitl_resolved": False,
            "hitl_awaiting": True,
            "hitl_pending": pending,
            "error": None,
            "artifacts": {
                **(state.get("artifacts") or {}),
                "hitl_async_session": session,
            },
            "messages": state.get("messages", [])
            + [f"HITL awaiting async approval ({n_gates} gate(s)); see hitl/async/"],
            "agent_messages": append_msg(state.get("agent_messages"), msg),
        }

    if auto:
        decisions = []
        patch: dict[str, Any] = {
            "hitl_pending": [],
            "hitl_resolved": True,
            "messages": state.get("messages", [])
            + [f"HITL auto-confirmed: {len(pending)} note(s), {len(options)} option-set(s)"],
        }
        arts = dict(state.get("artifacts") or {})
        for opt in options:
            key = opt.get("default") or "A"
            choice = next((c for c in opt.get("choices") or [] if c.get("key") == key), None)
            action = (choice or {}).get("action") or "accept_plan"
            decisions.append({"id": opt.get("id"), "key": key, "action": action, "auto": True})
            applied = _apply_action({**state, **patch, "artifacts": arts}, action)
            if applied.get("error"):
                return applied
            arts = applied.get("artifacts") or arts
            if "config" in applied:
                patch["config"] = applied["config"]
            if "dag" in applied:
                patch["dag"] = applied["dag"]
            patch.setdefault("messages", []).extend(applied.get("messages") or [])
        arts["hitl_decisions"] = decisions
        patch["artifacts"] = {**arts, "hitl_options": []}
        from metagenomic_agent.agents.hitl_gates import write_hitl_log

        log_path = write_hitl_log({**state, **patch, "artifacts": arts}, decisions)
        if log_path:
            arts["hitl_log"] = log_path
            patch["artifacts"] = {**arts, "hitl_options": []}
        msg = emit("hitl", "executor", "hitl", {"action": "auto_confirm", "decisions": decisions})
        patch["agent_messages"] = append_msg(state.get("agent_messages"), msg)
        return patch

    console.print("[yellow]Human-in-the-loop checkpoints:[/yellow]")
    for item in pending:
        console.print(f"  • {item}")

    arts = dict(state.get("artifacts") or {})
    patch: dict[str, Any] = {
        "hitl_pending": [],
        "hitl_resolved": True,
        "messages": list(state.get("messages") or []),
        "config": dict(state.get("config") or {}),
        "dag": list(state.get("dag") or []),
    }
    decisions = []

    for opt in options:
        console.print(f"\n[bold]{opt.get('question')}[/bold]")
        choices = opt.get("choices") or []
        for c in choices:
            console.print(f"  {c.get('key')}. {c.get('label')}")
        keys = [str(c.get("key")) for c in choices]
        default = str(opt.get("default") or (keys[0] if keys else "A"))
        key = Prompt.ask("Select", choices=keys or ["A", "B", "C"], default=default)
        choice = next((c for c in choices if str(c.get("key")) == key), None)
        action = (choice or {}).get("action") or "accept_plan"
        decisions.append({"id": opt.get("id"), "key": key, "action": action, "auto": False})
        applied = _apply_action({**state, **patch, "artifacts": arts}, action)
        if applied.get("hitl_resolved") is False:
            msg = emit("hitl", "system", "hitl", {"action": "abort", "decisions": decisions})
            applied["agent_messages"] = append_msg(state.get("agent_messages"), msg)
            return applied
        arts = applied.get("artifacts") or arts
        if "config" in applied:
            patch["config"] = applied["config"]
        if "dag" in applied:
            patch["dag"] = applied["dag"]
        patch["messages"].extend(applied.get("messages") or [])

    # Legacy binary confirm if only free-text pending and no structured options
    if pending and not options:
        ok = Confirm.ask("Proceed with planned workflow?", default=True)
        if not ok:
            msg = emit("hitl", "system", "hitl", {"action": "abort", "items": pending})
            return {
                "hitl_resolved": False,
                "error": "Aborted at HITL checkpoint",
                "messages": state.get("messages", []) + ["HITL: user aborted"],
                "agent_messages": append_msg(state.get("agent_messages"), msg),
                "dag": [],
            }

    arts["hitl_decisions"] = decisions
    arts["hitl_options"] = []
    patch["artifacts"] = arts
    from metagenomic_agent.agents.hitl_gates import write_hitl_log

    log_path = write_hitl_log({**state, **patch, "artifacts": arts}, decisions)
    if log_path:
        arts["hitl_log"] = log_path
        patch["artifacts"] = arts
    msg = emit("hitl", "executor", "hitl", {"action": "confirmed", "decisions": decisions})
    patch["agent_messages"] = append_msg(state.get("agent_messages"), msg)
    patch["messages"].append("HITL: user confirmed")
    return patch
