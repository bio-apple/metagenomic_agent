"""Technical QC validator."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_technical(state: dict[str, Any]) -> dict[str, Any]:
    cfg = state.get("config", {}).get("validation", {})
    min_retention = float(cfg.get("min_read_retention", 0.3))
    max_host = float(cfg.get("max_host_fraction", 0.95))
    qc = state.get("artifacts", {}).get("qc_host", {})
    tax = state.get("artifacts", {}).get("taxonomy", {})
    errors = state.get("artifacts", {}).get("errors", [])

    checks: dict[str, Any] = {"samples": {}, "ok": True, "messages": []}
    if errors:
        checks["ok"] = False
        checks["messages"].append(f"Execution errors present: {len(errors)}")

    for sample in state.get("samples", []):
        sid = sample["sample_id"]
        s_qc = qc.get(sid, {})
        s_tax = tax.get(sid, {})
        retention = float(s_qc.get("read_retention", 1.0))
        host_frac = float(s_qc.get("host_fraction", 0.0))
        abundance = s_tax.get("kraken2_abundance") or s_tax.get("metaphlan_abundance")
        abundance_ok = bool(abundance and Path(abundance).exists())
        sample_ok = retention >= min_retention and host_frac <= max_host and abundance_ok
        checks["samples"][sid] = {
            "read_retention": retention,
            "host_fraction": host_frac,
            "abundance_ok": abundance_ok,
            "ok": sample_ok,
        }
        if not sample_ok:
            checks["ok"] = False
            checks["messages"].append(
                f"{sid}: retention={retention:.2f}, host={host_frac:.2f}, abundance_ok={abundance_ok}"
            )
    return checks
