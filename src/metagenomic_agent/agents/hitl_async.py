"""Async HITL session store — API/Web approval without blocking CLI prompts."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def session_dir(outdir: str | Path) -> Path:
    d = Path(outdir) / "hitl" / "async"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_awaiting_session(state: dict[str, Any]) -> dict[str, Any]:
    """Persist pending gates + compact state for later resume."""
    outdir = state["outdir"]
    root = session_dir(outdir)
    options = list((state.get("artifacts") or {}).get("hitl_options") or [])
    pending = list(state.get("hitl_pending") or [])
    run_id = state.get("run_id") or "run"
    session = {
        "status": "awaiting_hitl",
        "run_id": run_id,
        "created_at": time.time(),
        "query": state.get("user_query"),
        "input_path": state.get("input_path"),
        "outdir": outdir,
        "mode": state.get("mode"),
        "pending": pending,
        "options": options,
        "resume_from": "execute_swarm",
    }
    (root / "session.json").write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    # Full state for resume (JSON-serializable subset)
    state_path = root / "state.json"
    slim = {
        k: state.get(k)
        for k in (
            "user_query",
            "input_path",
            "outdir",
            "mode",
            "config",
            "samples",
            "metadata_path",
            "tasks",
            "dag",
            "artifacts",
            "messages",
            "agent_messages",
            "validation",
            "critic",
            "literature",
            "statistics",
            "retry_count",
            "max_retries",
            "hitl_pending",
            "hitl_auto_confirm",
            "hitl_resolved",
            "report_path",
            "error",
            "run_id",
        )
        if k in state or True
    }
    slim["hitl_awaiting"] = True
    slim["hitl_resolved"] = False
    state_path.write_text(json.dumps(slim, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (root / "AWAITING.md").write_text(
        "# Awaiting Human-in-the-Loop approval\n\n"
        f"- run_id: `{run_id}`\n"
        f"- options: {len(options)}\n\n"
        "Approve via API:\n\n"
        "```bash\n"
        f"curl -X POST http://127.0.0.1:8000/runs/{run_id}/hitl/decide \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\"outdir\":\"" + str(outdir) + "\",\"decisions\":[{\"id\":\"confirm_assembly\",\"key\":\"A\"}]}'\n"
        "```\n",
        encoding="utf-8",
    )
    return {**session, "session_path": str(root / "session.json"), "state_path": str(state_path)}


def load_session(outdir: str | Path) -> dict[str, Any] | None:
    path = session_dir(outdir) / "session.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(outdir: str | Path) -> dict[str, Any] | None:
    path = session_dir(outdir) / "state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_decisions(outdir: str | Path, decisions: list[dict[str, Any]]) -> Path:
    root = session_dir(outdir)
    path = root / "decisions.json"
    path.write_text(json.dumps({"decisions": decisions, "decided_at": time.time()}, indent=2), encoding="utf-8")
    return path


def apply_decisions_to_state(state: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply API decisions (option id + key) onto state via HITL actions."""
    from metagenomic_agent.agents.hitl import _apply_action

    options = {(o.get("id")): o for o in ((state.get("artifacts") or {}).get("hitl_options") or [])}
    # Also load from session file if state options cleared
    sess = load_session(state["outdir"])
    if sess and sess.get("options"):
        for o in sess["options"]:
            options.setdefault(o.get("id"), o)

    patch: dict[str, Any] = {
        "config": dict(state.get("config") or {}),
        "dag": list(state.get("dag") or []),
        "artifacts": dict(state.get("artifacts") or {}),
        "messages": list(state.get("messages") or []),
    }
    arts = patch["artifacts"]
    applied_log = []
    for dec in decisions:
        oid = dec.get("id")
        key = str(dec.get("key") or "")
        opt = options.get(oid) or {}
        choice = next((c for c in (opt.get("choices") or []) if str(c.get("key")) == key), None)
        action = dec.get("action") or (choice or {}).get("action")
        if not action:
            continue
        applied = _apply_action(
            {
                **state,
                "config": patch["config"],
                "dag": patch["dag"],
                "artifacts": arts,
            },
            action,
        )
        if applied.get("error"):
            return {**state, **applied, "hitl_awaiting": False}
        arts = applied.get("artifacts") or arts
        if "config" in applied:
            patch["config"] = applied["config"]
        if "dag" in applied:
            patch["dag"] = applied["dag"]
        patch["messages"].extend(applied.get("messages") or [])
        applied_log.append({"id": oid, "key": key, "action": action, "auto": False, "source": "api"})

    arts["hitl_decisions"] = applied_log
    arts["hitl_options"] = []
    from metagenomic_agent.agents.hitl_gates import write_hitl_log

    write_hitl_log({**state, **patch, "artifacts": arts}, applied_log)
    save_decisions(state["outdir"], applied_log)
    # Mark session resolved
    sess_path = session_dir(state["outdir"]) / "session.json"
    if sess_path.exists():
        sess = json.loads(sess_path.read_text(encoding="utf-8"))
        sess["status"] = "decided"
        sess["decisions"] = applied_log
        sess_path.write_text(json.dumps(sess, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        **state,
        "config": patch["config"],
        "dag": patch["dag"],
        "artifacts": arts,
        "messages": patch["messages"],
        "hitl_pending": [],
        "hitl_resolved": True,
        "hitl_awaiting": False,
        "hitl_auto_confirm": True,  # remaining mid-swarm gates use recorded flags
        "error": None,
    }
