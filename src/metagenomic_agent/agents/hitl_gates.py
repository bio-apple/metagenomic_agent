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
        "label": "严格：患病率≥20% 且 相对丰度≥0.01%",
    },
    "balanced": {
        "min_prevalence": 0.1,
        "min_rel_abundance": 1e-5,
        "label": "均衡：患病率≥10% 且 相对丰度≥0.001%（推荐）",
    },
    "lenient": {
        "min_prevalence": 0.05,
        "min_rel_abundance": 1e-6,
        "label": "宽松：患病率≥5% 且 相对丰度≥0.0001%",
    },
    "none": {
        "min_prevalence": 0.0,
        "min_rel_abundance": 0.0,
        "label": "不剔除极低频特征（保留全部）",
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
    wall_s = f"{wall:.2f} h" if wall is not None else "数小时级"
    mem_s = asm_est.get("est_mem_gb") or mem or "?"
    question = (
        f"[Assembly] 即将提交高算力组装/分箱（assembler=`{assembler}`，n={n}）。"
        f"预估墙钟 ≈ {wall_s}，内存 ≈ {mem_s} GB"
        + (f"（申请 {threads} CPU / {mem} GB）" if threads and mem else "")
        + "。请确认："
    )
    return {
        "id": "confirm_assembly",
        "gate": "assembly_compute",
        "critical": True,
        "question": question,
        "choices": [
            {
                "key": "A",
                "label": f"确认提交 Assembly（{assembler}）",
                "action": "confirm_assembly",
            },
            {
                "key": "B",
                "label": "改用更省内存的 MEGAHIT 后提交",
                "action": "confirm_assembly_megahit",
            },
            {
                "key": "C",
                "label": "跳过 Assembly/分箱（节省算力）",
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
        "[OTU/ASV 过滤] 差异/多样性分析前将剔除极低频特征。"
        f"当前默认 prevalence≥{cur_prev} · rel_abundance≥{cur_ab}。"
        "请选择阈值（生信人员确认后再继续）："
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
            f"[Databases] 参考库路径需确认后再跑分类/MAG（{detail}）。"
            "请确认已下载/挂载 BioContainers 配套库："
        ),
        "choices": [
            {"key": "A", "label": "已就绪，继续分析", "action": "confirm_databases"},
            {"key": "B", "label": "仅用已有库，跳过缺失库相关步骤", "action": "databases_partial"},
            {"key": "C", "label": "中止，先去下载/配置 paths.*", "action": "abort_for_databases"},
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
            "[Report] 即将生成并可外发最终报告（HTML/手稿草稿）。"
            "请确认是否允许写入 final_report 并标记为可分享："
        ),
        "choices": [
            {"key": "A", "label": "允许生成并标记可外发", "action": "publish_report"},
            {"key": "B", "label": "仅内部草稿（不标记外发）", "action": "draft_report_only"},
            {"key": "C", "label": "暂缓报告生成", "action": "hold_report"},
        ],
        "default": str(hitl_cfg.get("default_report_publish") or "B"),
        "context": {"outdir": state.get("outdir")},
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
