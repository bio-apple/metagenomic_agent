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
    from metagenomic_agent.validators.bio_qc import check_mag_qc, check_taxonomy_qc

    cfg = state.get("config", {})
    vcfg = cfg.get("validation", {})
    min_retention = float(vcfg.get("min_read_retention", 0.3))
    max_host = float(vcfg.get("max_host_fraction", 0.95))
    qc = state.get("artifacts", {}).get("qc_host", {})
    tax = state.get("artifacts", {}).get("taxonomy", {})
    assembly = state.get("artifacts", {}).get("assembly", {})
    errors = state.get("artifacts", {}).get("errors", [])

    checks: dict[str, Any] = {"samples": {}, "mags": {}, "taxonomy_qc": {}, "ok": True, "messages": []}
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
        abundance_ok = bool(abundance and Path(str(abundance)).exists()) if abundance else bool(s_tax)
        sample_ok = retention >= min_retention and host_frac <= max_host and (abundance_ok or state.get("mode") == "mock")
        tqc = check_taxonomy_qc(
            classification_rate=s_tax.get("classification_rate"),
            unclassified_fraction=s_tax.get("unclassified_fraction"),
            sample_id=sid,
            config=cfg,
            report_path=s_tax.get("kraken2_report"),
        )
        checks["taxonomy_qc"][sid] = tqc
        if not tqc["ok"]:
            sample_ok = False
            checks["messages"].extend(tqc["warnings"])
        checks["samples"][sid] = {
            "read_retention": retention,
            "host_fraction": host_frac,
            "abundance_ok": abundance_ok,
            "classification_rate": tqc.get("classification_rate"),
            "unclassified_fraction": tqc.get("unclassified_fraction"),
            "ok": sample_ok,
        }
        if not sample_ok:
            checks["ok"] = False
            checks["messages"].append(
                f"{sid}: retention={retention:.2f}, host={host_frac:.2f}, abundance_ok={abundance_ok}"
            )

        s_asm = assembly.get(sid) or {}
        if s_asm and not s_asm.get("error"):
            checkm_rows = _parse_checkm(s_asm.get("checkm2"))
            comp = s_asm.get("completeness")
            cont = s_asm.get("contamination")
            if comp is None and checkm_rows:
                comp = checkm_rows[0]["completeness"]
            if cont is None and checkm_rows:
                cont = checkm_rows[0]["contamination"]
            n_bins = int(s_asm.get("n_bins") or len(checkm_rows) or 0)
            mqc = check_mag_qc(
                completeness=float(comp) if comp is not None else None,
                contamination=float(cont) if cont is not None else None,
                sample_id=sid,
                n_bins=n_bins,
                config=cfg,
            )
            # Technical hard-fail uses medium gate (ok=False on low/fail)
            mag_ok = n_bins > 0 and mqc["ok"]
            checks["mags"][sid] = {**mqc, "ok": mag_ok}
            if not mag_ok:
                checks["ok"] = False
                checks["messages"].append(
                    f"{sid} MAG QC fail: tier={mqc.get('tier')} bins={n_bins}, "
                    f"completeness={comp}, contamination={cont}"
                )
    return checks
