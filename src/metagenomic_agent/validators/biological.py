"""Biological consistency checks for gut metagenomes."""

from __future__ import annotations

from typing import Any


def validate_biological(state: dict[str, Any]) -> dict[str, Any]:
    cfg = state.get("config", {}).get("validation", {})
    require = bool(cfg.get("require_gut_markers", True))
    markers = set(cfg.get("gut_marker_genera", []))
    tax = state.get("artifacts", {}).get("taxonomy", {})
    query = (state.get("user_query") or "").lower()
    gut_like = any(k in query for k in ("gut", "肠道", "粪", "stool", "fecal"))

    result: dict[str, Any] = {"samples": {}, "ok": True, "messages": []}
    if not require or not gut_like:
        result["messages"].append("Biological gut-marker check skipped")
        return result

    for sample in state.get("samples", []):
        sid = sample["sample_id"]
        top = set(tax.get(sid, {}).get("top_genera", []))
        hit = sorted(top & markers)
        ok = len(hit) >= 1
        result["samples"][sid] = {"marker_hits": hit, "ok": ok}
        if not ok:
            result["ok"] = False
            result["messages"].append(f"{sid}: no gut marker genera in top list {sorted(top)}")
    return result
