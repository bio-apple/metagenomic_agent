"""Technical QC validator including MAG CheckM thresholds."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _parse_checkm(path: str | None) -> list[dict[str, float]]:
    if not path or not Path(path).exists():
        return []
    rows = []
    lines = Path(path).read_text().splitlines()
    if not lines:
        return []
    header = lines[0].lower()
    for line in lines[1:]:
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        try:
            # flexible: Name Completeness Contamination
            if "completeness" in header:
                rows.append({"completeness": float(parts[1]), "contamination": float(parts[2])})
            else:
                rows.append({"completeness": float(parts[1]), "contamination": float(parts[2])})
        except ValueError:
            continue
    return rows


def validate_technical(state: dict[str, Any]) -> dict[str, Any]:
    cfg = state.get("config", {}).get("validation", {})
    min_retention = float(cfg.get("min_read_retention", 0.3))
    max_host = float(cfg.get("max_host_fraction", 0.95))
    min_comp = float(cfg.get("min_mag_completeness", 50))
    max_cont = float(cfg.get("max_mag_contamination", 10))
    qc = state.get("artifacts", {}).get("qc_host", {})
    tax = state.get("artifacts", {}).get("taxonomy", {})
    assembly = state.get("artifacts", {}).get("assembly", {})
    errors = state.get("artifacts", {}).get("errors", [])

    checks: dict[str, Any] = {"samples": {}, "mags": {}, "ok": True, "messages": []}
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

        # MAG QC when assembly artifacts exist
        s_asm = assembly.get(sid) or {}
        if s_asm and not s_asm.get("error"):
            checkm_rows = _parse_checkm(s_asm.get("checkm2"))
            comp = float(s_asm.get("completeness") or (checkm_rows[0]["completeness"] if checkm_rows else 0))
            cont = float(s_asm.get("contamination") or (checkm_rows[0]["contamination"] if checkm_rows else 100))
            n_bins = int(s_asm.get("n_bins") or len(checkm_rows) or 0)
            mag_ok = n_bins > 0 and comp >= min_comp and cont <= max_cont
            checks["mags"][sid] = {
                "n_bins": n_bins,
                "completeness": comp,
                "contamination": cont,
                "ok": mag_ok,
            }
            if not mag_ok:
                checks["ok"] = False
                checks["messages"].append(
                    f"{sid} MAG QC fail: bins={n_bins}, completeness={comp:.1f}, contamination={cont:.1f}"
                )
    return checks
