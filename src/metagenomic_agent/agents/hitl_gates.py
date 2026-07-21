"""Critical Human-in-the-Loop gates — assembly compute & OTU/ASV prevalence filters.

Bioinformaticians must confirm before heavy Assembly submission or rare-feature culling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt

console = Console()

# Suggested prevalence cutoffs for ultra-low-frequency OTU/ASV/genus features
OTU_THRESHOLD_PRESETS: dict[str, dict[str, Any]] = {
    "strict": {
        "min_prevalence": 0.2,
        "min_rel_abundance": 1e-4,
        "label": "Strict: prevalence ≥20% and relative abundance ≥0.01%",
    },
    "balanced": {
        "min_prevalence": 0.1,
        "min_rel_abundance": 1e-5,
        "label": "Balanced: prevalence ≥10% and relative abundance ≥0.001% (recommended)",
    },
    "lenient": {
        "min_prevalence": 0.05,
        "min_rel_abundance": 1e-6,
        "label": "Lenient: prevalence ≥5% and relative abundance ≥0.0001%",
    },
    "none": {
        "min_prevalence": 0.0,
        "min_rel_abundance": 0.0,
        "label": "Do not filter ultra-rare features (keep all)",
    },
}


def _assembly_planned(state: dict[str, Any]) -> bool:
    if any(n.get("agent") == "assembly" and n.get("status") != "skipped" for n in (state.get("dag") or [])):
        return True
    bio = (state.get("artifacts") or {}).get("bio_reasoning") or {}
    pipe = (state.get("config") or {}).get("pipeline") or {}
    return bool(bio.get("enable_assembly") or pipe.get("enable_assembly"))


def _statistics_planned(state: dict[str, Any]) -> bool:
    if any(
        n.get("agent") in {"statistics", "stats"} and n.get("status") != "skipped"
        for n in (state.get("dag") or [])
    ):
        return True
    bio = (state.get("artifacts") or {}).get("bio_reasoning") or {}
    pipe = (state.get("config") or {}).get("pipeline") or {}
    return bool(bio.get("enable_statistics") or pipe.get("enable_statistics"))


def build_assembly_gate(state: dict[str, Any]) -> dict[str, Any] | None:
    """Option set shown before submitting compute-heavy assembly."""
    if not _assembly_planned(state):
        return None
    hitl_cfg = (state.get("config") or {}).get("hitl") or {}
    if hitl_cfg.get("require_assembly_confirm", True) is False:
        return None
    estimate = (state.get("artifacts") or {}).get("resource_estimate") or {}
    stages = {s.get("agent"): s for s in (estimate.get("stages") or [])}
    asm_est = stages.get("assembly") or {}
    alloc = ((state.get("artifacts") or {}).get("executor") or {}).get("allocation") or {}
    threads = alloc.get("threads") or (state.get("config") or {}).get("linux", {}).get("threads")
    mem = alloc.get("memory_gb") or (state.get("config") or {}).get("linux", {}).get("memory_gb")
    bio = (state.get("artifacts") or {}).get("bio_reasoning") or {}
    assembler = bio.get("assembler_preference") or "megahit"
    n = len(state.get("samples") or [])
    wall = asm_est.get("est_wall_hours")
    wall_s = f"{wall:.2f} h" if wall is not None else "several hours"
    mem_s = asm_est.get("est_mem_gb") or mem or "?"
    question = (
        f"[Assembly] About to submit compute-heavy assembly/binning "
        f"(assembler=`{assembler}`, n={n}). "
        f"Estimated wall time ≈ {wall_s}, memory ≈ {mem_s} GB"
        + (f" (requesting {threads} CPU / {mem} GB)" if threads and mem else "")
        + ". Please confirm:"
    )
    return {
        "id": "confirm_assembly",
        "gate": "assembly_compute",
        "critical": True,
        "question": question,
        "choices": [
            {
                "key": "A",
                "label": f"Confirm and submit Assembly ({assembler})",
                "action": "confirm_assembly",
            },
            {
                "key": "B",
                "label": "Switch to memory-efficient MEGAHIT, then submit",
                "action": "confirm_assembly_megahit",
            },
            {
                "key": "C",
                "label": "Skip Assembly/binning (save compute)",
                "action": "skip_assembly",
            },
        ],
        "default": "A" if hitl_cfg.get("default_confirm_assembly", True) else "C",
        "context": {
            "assembler": assembler,
            "n_samples": n,
            "est_wall_hours": wall,
            "est_mem_gb": mem_s,
        },
    }


def build_otu_filter_gate(state: dict[str, Any]) -> dict[str, Any] | None:
    """Option set for ultra-low-frequency OTU/ASV (genus-feature) culling thresholds."""
    if not _statistics_planned(state):
        return None
    hitl_cfg = (state.get("config") or {}).get("hitl") or {}
    if hitl_cfg.get("require_otu_filter_confirm", True) is False:
        return None
    stats_cfg = (state.get("config") or {}).get("statistics") or {}
    cur_prev = stats_cfg.get("min_prevalence", 0.1)
    cur_ab = stats_cfg.get("min_rel_abundance", 1e-5)
    question = (
        "[OTU/ASV filter] Ultra-rare features will be removed before differential/diversity analysis. "
        f"Current defaults: prevalence≥{cur_prev} · rel_abundance≥{cur_ab}. "
        "Please select thresholds (bioinformatician confirmation required):"
    )
    return {
        "id": "confirm_otu_asv_filter",
        "gate": "otu_asv_prevalence",
        "critical": True,
        "question": question,
        "choices": [
            {"key": "A", "label": OTU_THRESHOLD_PRESETS["balanced"]["label"], "action": "otu_filter_balanced"},
            {"key": "B", "label": OTU_THRESHOLD_PRESETS["strict"]["label"], "action": "otu_filter_strict"},
            {"key": "C", "label": OTU_THRESHOLD_PRESETS["lenient"]["label"], "action": "otu_filter_lenient"},
            {"key": "D", "label": OTU_THRESHOLD_PRESETS["none"]["label"], "action": "otu_filter_none"},
        ],
        "default": str(hitl_cfg.get("default_otu_filter") or "A"),
        "context": {"current_min_prevalence": cur_prev, "current_min_rel_abundance": cur_ab},
    }


def build_database_gate(state: dict[str, Any]) -> dict[str, Any] | None:
    """Confirm reference DB paths before taxonomy/MAG steps (download / mount)."""
    hitl_cfg = (state.get("config") or {}).get("hitl") or {}
    if hitl_cfg.get("require_database_confirm", True) is False:
        return None
    paths = (state.get("config") or {}).get("paths") or {}
    mode = state.get("mode") or "mock"
    if mode == "mock":
        return None
    missing = []
    for key in ("kraken2_db", "gtdb", "host_index", "metaphlan_db"):
        val = (paths.get(key) or "").strip()
        if not val or val.startswith("<"):
            missing.append(key)
            continue
        p = Path(val)
        if not p.exists():
            missing.append(f"{key} (missing: {val})")
    if not missing and hitl_cfg.get("database_confirm_only_when_missing", True):
        return None
    detail = ", ".join(missing) if missing else "paths look present"
    return {
        "id": "confirm_databases",
        "gate": "database_download",
        "critical": True,
        "question": (
            f"[Databases] Reference database paths must be confirmed before taxonomy/MAG ({detail}). "
            "Please confirm BioContainers companion databases are downloaded/mounted:"
        ),
        "choices": [
            {"key": "A", "label": "Ready — continue analysis", "action": "confirm_databases"},
            {"key": "B", "label": "Use available DBs only; skip steps needing missing DBs", "action": "databases_partial"},
            {"key": "C", "label": "Abort — download/configure paths.* first", "action": "abort_for_databases"},
        ],
        "default": "A",
        "context": {"missing": missing, "paths": {k: paths.get(k) for k in ("kraken2_db", "gtdb", "host_index")}},
    }


def build_report_publish_gate(state: dict[str, Any]) -> dict[str, Any] | None:
    """Confirm before publishing / exporting final report externally."""
    hitl_cfg = (state.get("config") or {}).get("hitl") or {}
    if hitl_cfg.get("require_report_publish_confirm", True) is False:
        return None
    return {
        "id": "confirm_report_publish",
        "gate": "report_publish",
        "critical": True,
        "question": (
            "[Report] About to generate a final report that may be shared externally (HTML/manuscript draft). "
            "Confirm writing final_report and marking it as shareable:"
        ),
        "choices": [
            {"key": "A", "label": "Allow generation and mark as shareable", "action": "publish_report"},
            {"key": "B", "label": "Internal draft only (do not mark shareable)", "action": "draft_report_only"},
            {"key": "C", "label": "Hold report generation", "action": "hold_report"},
        ],
        "default": str(hitl_cfg.get("default_report_publish") or "B"),
        "context": {"outdir": state.get("outdir")},
    }


def build_self_heal_gate(state: dict[str, Any], proposed: list[str] | None = None) -> dict[str, Any] | None:
    """Confirm before applying high-risk self-heal actions that can change biology."""
    hitl_cfg = (state.get("config") or {}).get("hitl") or {}
    if hitl_cfg.get("require_self_heal_confirm", True) is False:
        return None
    from metagenomic_agent.execution.self_heal import HIGH_RISK_ACTIONS, partition_actions

    proposed = list(
        proposed
        if proposed is not None
        else ((state.get("artifacts") or {}).get("self_heal_proposed") or [])
    )
    parts = partition_actions(proposed)
    if not parts["high"]:
        return None
    high = ", ".join(parts["high"])
    safe = ", ".join(parts["medium"] + parts["low"]) or "(none)"
    return {
        "id": "confirm_self_heal",
        "gate": "self_heal_high_risk",
        "critical": True,
        "question": (
            "[Self-Heal] Auto-recovery proposes high-risk actions that may change biological conclusions: "
            f"{high}. Safe actions: {safe}. Please choose:"
        ),
        "choices": [
            {
                "key": "A",
                "label": f"Approve all actions (including high-risk: {high})",
                "action": "approve_all_heal",
            },
            {
                "key": "B",
                "label": "Run safe actions only (defer high-risk) — recommended",
                "action": "approve_safe_heal_only",
            },
            {
                "key": "C",
                "label": "Reject self-heal; keep original errors for Critic/report",
                "action": "reject_heal",
            },
        ],
        "default": str(hitl_cfg.get("default_self_heal") or "B"),
        "context": {
            "proposed": proposed,
            "high_risk": parts["high"],
            "safe": parts["medium"] + parts["low"],
            "high_risk_catalog": sorted(HIGH_RISK_ACTIONS),
        },
    }


def register_critical_gates(state: dict[str, Any]) -> dict[str, Any]:
    """Merge critical gates into hitl_options / hitl_pending (idempotent by id)."""
    arts = dict(state.get("artifacts") or {})
    options = list(arts.get("hitl_options") or [])
    pending = list(state.get("hitl_pending") or [])
    existing = {o.get("id") for o in options}
    registered = []

    for builder in (
        build_assembly_gate,
        build_otu_filter_gate,
        build_database_gate,
        build_report_publish_gate,
    ):
        gate = builder(state)
        if not gate or gate["id"] in existing:
            continue
        options.append(gate)
        pending.append(f"[HITL:{gate['gate']}] {gate['question'][:120]}")
        registered.append(gate["id"])
        existing.add(gate["id"])

    arts["hitl_options"] = options
    arts["hitl_critical_gates"] = list(dict.fromkeys(list(arts.get("hitl_critical_gates") or []) + registered))
    return {
        "artifacts": arts,
        "hitl_pending": pending,
        "messages": (state.get("messages") or [])
        + ([f"HITL critical gates registered: {registered}"] if registered else []),
    }


def apply_otu_preset(config: dict[str, Any], preset: str) -> dict[str, Any]:
    cfg = dict(config)
    stats = dict(cfg.get("statistics") or {})
    p = OTU_THRESHOLD_PRESETS.get(preset) or OTU_THRESHOLD_PRESETS["balanced"]
    stats["min_prevalence"] = p["min_prevalence"]
    stats["min_rel_abundance"] = p["min_rel_abundance"]
    stats["otu_filter_preset"] = preset
    cfg["statistics"] = stats
    return cfg


def write_hitl_log(state: dict[str, Any], decisions: list[dict[str, Any]]) -> str | None:
    outdir = state.get("outdir")
    if not outdir:
        return None
    out = Path(outdir) / "hitl"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "critical_gates.json"
    payload = {
        "decisions": decisions,
        "gates": (state.get("artifacts") or {}).get("hitl_critical_gates"),
        "statistics_filter": (state.get("config") or {}).get("statistics"),
        "assembly_enabled": _assembly_planned(state),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "CRITICAL_GATES.md").write_text(
        "# Human-in-the-Loop critical gates\n\n"
        + "\n".join(
            f"- `{d.get('id')}` → {d.get('key')} / `{d.get('action')}` (auto={d.get('auto')})"
            for d in decisions
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


def confirm_gate_inline(
    state: dict[str, Any],
    gate: dict[str, Any],
    *,
    auto: bool,
) -> tuple[str, dict[str, Any]]:
    """Resolve a single gate mid-swarm; returns (action, patch)."""
    from metagenomic_agent.agents.hitl import _apply_action

    if auto:
        key = gate.get("default") or "A"
        choice = next((c for c in gate.get("choices") or [] if c.get("key") == key), None)
        action = (choice or {}).get("action") or "confirm_assembly"
        return action, _apply_action(state, action)

    console.print(f"\n[yellow]Critical HITL gate:[/yellow] [bold]{gate.get('question')}[/bold]")
    choices = gate.get("choices") or []
    for c in choices:
        console.print(f"  {c.get('key')}. {c.get('label')}")
    keys = [str(c.get("key")) for c in choices]
    default = str(gate.get("default") or (keys[0] if keys else "A"))
    if not keys:
        ok = Confirm.ask("Proceed?", default=True)
        action = "confirm_assembly" if ok else "skip_assembly"
        return action, _apply_action(state, action)
    key = Prompt.ask("Select", choices=keys, default=default)
    choice = next((c for c in choices if str(c.get("key")) == key), None)
    action = (choice or {}).get("action") or "confirm_assembly"
    return action, _apply_action(state, action)
