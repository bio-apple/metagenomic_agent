"""Context-aware biological consistency validation (anti Garbage-In-Gospel-Out)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KB_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "ibd_biomarker_kb.json"


def _load_kb() -> dict[str, Any]:
    if KB_PATH.exists():
        return json.loads(KB_PATH.read_text(encoding="utf-8"))
    return {"contexts": {}}


def _infer_context(query: str, kb: dict[str, Any]) -> str | None:
    q = query.lower()
    for name, ctx in (kb.get("contexts") or {}).items():
        for alias in ctx.get("aliases") or []:
            if alias.lower() in q:
                return name
    return None


def _top_genera(tax: dict[str, Any]) -> list[str]:
    tops: list[str] = []
    for art in tax.values():
        tops.extend(art.get("top_genera") or [])
        for item in (art.get("fusion") or {}).get("fused_genera") or []:
            if isinstance(item, dict) and item.get("genus"):
                tops.append(item["genus"])
    return list(dict.fromkeys(tops))


def validate_biological(state: dict[str, Any]) -> dict[str, Any]:
    cfg = state.get("config", {}).get("validation", {})
    require = bool(cfg.get("require_gut_markers", True))
    markers = set(cfg.get("gut_marker_genera", []))
    tax = state.get("artifacts", {}).get("taxonomy", {})
    query = state.get("user_query") or ""
    qlow = query.lower()
    gut_like = any(k in qlow for k in ("gut", "肠道", "粪", "stool", "fecal", "ibd", "炎症", "healthy", "健康"))

    result: dict[str, Any] = {
        "samples": {},
        "ok": True,
        "messages": [],
        "warnings": [],
        "context": None,
        "context_checks": [],
    }
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

    # Context-aware KB checks
    kb = _load_kb()
    ctx_name = _infer_context(query, kb)
    result["context"] = ctx_name
    if not ctx_name:
        return result

    ctx = kb["contexts"][ctx_name]
    tops = _top_genera(tax)
    top_set = set(tops)

    # Pathogen alert in healthy / soft contexts
    pathogens = set(ctx.get("pathogen_alert") or [])
    pathogen_hits = sorted(top_set & pathogens)
    if pathogen_hits and ctx_name in {"healthy_gut", "ibd"}:
        msg = (
            f"Context '{ctx_name}': unexpected high-concern taxa in top genera: {pathogen_hits}. "
            "Flagging for human review (possible contamination or mislabeled cohort)."
        )
        result["warnings"].append(msg)
        result["context_checks"].append({"type": "pathogen_alert", "hits": pathogen_hits})
        # Warning does not fail technical pipeline but marks biological caution
        result["messages"].append(msg)

    # IBD directional soft checks using biomarker table if available
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    biomarkers = stats.get("biomarker_list") or []
    if ctx_name == "ibd" and biomarkers:
        depleted_expected = set(ctx.get("expected_depleted") or [])
        enriched_expected = set(ctx.get("expected_enriched") or [])
        for b in biomarkers:
            genus = b.get("genus")
            direction = (b.get("direction") or "").lower()
            if genus in depleted_expected and "enriched_in_ibd" in direction:
                w = f"IBD KB conflict: {genus} expected depleted in IBD but direction={direction}"
                result["warnings"].append(w)
                result["context_checks"].append({"type": "direction_conflict", "genus": genus, "direction": direction})
            if genus in enriched_expected and "enriched_in_control" in direction:
                w = f"IBD KB conflict: {genus} expected enriched in IBD but direction={direction}"
                result["warnings"].append(w)
                result["context_checks"].append({"type": "direction_conflict", "genus": genus, "direction": direction})

    if ctx_name == "healthy_gut":
        expected = set(ctx.get("expected_enriched") or [])
        if tops and not (top_set & expected):
            w = f"Healthy-gut context but none of expected commensals {sorted(expected)[:5]} in tops {tops[:5]}"
            result["warnings"].append(w)
            result["messages"].append(w)

    # Persist for report highlighting
    out = Path(state["outdir"]) / "biological_context.json"
    out.write_text(
        json.dumps(
            {
                "context": ctx_name,
                "warnings": result["warnings"],
                "checks": result["context_checks"],
                "notes": ctx.get("notes"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result["report_path"] = str(out)
    return result
