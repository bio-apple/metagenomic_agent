"""Assembly & Binning Agent — MEGAHIT/metaSPAdes → MetaBAT2/MaxBin2 → CheckM2 → GTDB-Tk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import binning, megahit
from metagenomic_agent.tools.context import ToolContext
from metagenomic_agent.tools.linux_runner import classify_error


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    params = (node or {}).get("params") or {}
    bio = (state.get("artifacts") or {}).get("bio_reasoning") or {}
    assembler = (params.get("assembler") or bio.get("assembler_preference") or "megahit").lower()
    # Complexity heuristic: high → MEGAHIT; low → metaSPAdes (unless explicitly set)
    if not params.get("assembler") and bio.get("high_complexity") is False:
        assembler = "metaspades"
    binners = list(params.get("binners") or ["metabat2", "maxbin2"])
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    per_sample: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        asm_dir = outdir / sid / "assembly"
        try:
            if assembler == "metaspades":
                try:
                    asm = binning.run_metaspades(sample, upstream, asm_dir, ctx)
                except Exception as exc:  # noqa: BLE001 — self-heal: fall back to MEGAHIT
                    errors.append(
                        {
                            "node": f"assembly:{sid}:metaspades",
                            "error": str(exc),
                            "classified": classify_error(
                                getattr(ctx.last_result, "returncode", None),
                                str(exc),
                            ),
                        }
                    )
                    asm = megahit.run(sample, upstream, asm_dir, ctx=ctx)
                    asm["assembler"] = "megahit"
                    asm["fallback_from"] = "metaspades"
            else:
                asm = megahit.run(sample, upstream, asm_dir, ctx=ctx)
                asm["assembler"] = asm.get("assembler") or "megahit"

            contigs = asm.get("contigs")
            if contigs:
                bin_dir = outdir / sid / "binning"
                bins = binning.run_binning(sid, contigs, upstream, bin_dir, ctx, binners=binners)
                check = binning.run_checkm2(bins.get("bins_dir", str(bin_dir / "bins")), bin_dir, ctx, sid)
                gtdb = binning.run_gtdbtk(bins.get("bins_dir", str(bin_dir / "bins")), bin_dir, ctx, sid)
                asm = {**asm, **bins, **check, **gtdb}
            per_sample[sid] = asm
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "node": f"assembly:{sid}",
                    "error": str(exc),
                    "classified": classify_error(None, str(exc)),
                    "returncode": getattr(ctx.last_result, "returncode", None),
                }
            )
            per_sample[sid] = {"error": str(exc), "status": "failed"}

    result: dict[str, Any] = {"assembly": per_sample}
    if errors:
        result["errors"] = errors
    # Write MAG summary
    mag_dir = outdir / "mags"
    mag_dir.mkdir(parents=True, exist_ok=True)
    rows = ["sample\tassembler\tn_bins\tcompleteness\tcontamination\tgtdb"]
    for sid, art in per_sample.items():
        rows.append(
            f"{sid}\t{art.get('assembler', '')}\t{art.get('n_bins', '')}\t"
            f"{art.get('completeness', '')}\t{art.get('contamination', '')}\t{art.get('gtdb_summary', '')}"
        )
    (mag_dir / "mag_summary.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    result["mag_summary"] = str(mag_dir / "mag_summary.tsv")
    return result
