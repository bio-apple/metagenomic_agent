"""Assembly & Binning Agent — MEGAHIT/metaSPAdes → MetaBAT2/MaxBin2 → CheckM2 → GTDB-Tk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.execution.checkpoint import load_assembly_checkpoint, write_assembly_checkpoint
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
    pipe_bins = ((state.get("config") or {}).get("pipeline") or {}).get("binners")
    binners = list(params.get("binners") or pipe_bins or ["metabat2", "maxbin2", "concoct"])
    qc_arts = state.get("artifacts", {}).get("qc_host", {})
    cache_cfg = (state.get("config") or {}).get("cache") or {}
    per_sample_ckpt = bool(cache_cfg.get("per_sample_assembly", True))
    per_sample: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    checkpoints_reused = 0

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        asm_dir = outdir / sid / "assembly"
        try:
            # Checkpoint: reuse MEGAHIT/SPAdes contigs when re-asking / tweaking downstream
            cached = load_assembly_checkpoint(asm_dir, sid) if per_sample_ckpt else None
            if cached and cached.get("contigs"):
                asm = dict(cached)
                checkpoints_reused += 1
            elif assembler == "flye":
                from metagenomic_agent.tools import flye as flye_tool

                asm = flye_tool.run(sample, upstream, asm_dir, ctx=ctx)
                asm["assembler"] = "flye"
            elif assembler == "metaspades":
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
                # Always persist assembly checkpoint for long-running assemblers
                write_assembly_checkpoint(asm_dir, asm)
                bin_dir = outdir / sid / "binning"
                # Skip re-binning only when full MAG summary already present
                mag_done = (bin_dir / "bins").exists() and asm.get("n_bins")
                if asm.get("checkpoint") and mag_done:
                    pass
                else:
                    bins = binning.run_binning(sid, contigs, upstream, bin_dir, ctx, binners=binners)
                    if "vamb" in [b.lower() for b in binners]:
                        from metagenomic_agent.tools import vamb as vamb_tool

                        vamb_art = vamb_tool.run_vamb(sid, contigs, bin_dir / "vamb", ctx)
                        bins = {**bins, **vamb_art}
                    # DAS Tool refinement across binners
                    from metagenomic_agent.tools import das_tool as das_tool_mod

                    sources: dict[str, str] = {}
                    for key, label in (
                        ("metabat2_dir", "metabat"),
                        ("maxbin2_dir", "maxbin"),
                        ("concoct_dir", "concoct"),
                        ("vamb_bins_dir", "vamb"),
                        ("das_tool_dir", "pre"),
                        ("bins_dir", "bins"),
                    ):
                        if bins.get(key):
                            sources[label] = str(bins[key])
                    if len(sources) >= 1:
                        das = das_tool_mod.run_das_tool(sid, contigs, sources, bin_dir / "das_tool", ctx)
                        bins = {**bins, **das}
                    check = binning.run_checkm2(bins.get("bins_dir", str(bin_dir / "bins")), bin_dir, ctx, sid)
                    from metagenomic_agent.tools import busco as busco_tool

                    busco = busco_tool.run_busco(
                        bins.get("bins_dir", str(bin_dir / "bins")), bin_dir, ctx, sid
                    )
                    gtdb = binning.run_gtdbtk(bins.get("bins_dir", str(bin_dir / "bins")), bin_dir, ctx, sid)
                    asm = {**asm, **bins, **check, **busco, **gtdb}
                    pipe = (state.get("config") or {}).get("pipeline") or {}
                    if pipe.get("enable_virus", False):
                        from metagenomic_agent.tools import virus as virus_tools

                        asm["virus"] = virus_tools.run_virus_suite(
                            contigs, outdir / sid / "virus", ctx, sid
                        )
                    write_assembly_checkpoint(asm_dir, asm)
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

    result: dict[str, Any] = {
        "assembly": per_sample,
        "assembly_checkpoints_reused": checkpoints_reused,
    }
    if errors:
        result["errors"] = errors
    # Write MAG summary (HQ / MQ / LQ counts)
    mag_dir = outdir / "mags"
    mag_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        "sample\tassembler\tn_bins\tcompleteness\tcontamination\tbusco_complete\tquality_class\tgtdb"
    ]
    hq = mq = lq = 0
    for sid, art in per_sample.items():
        try:
            comp = float(art.get("completeness") or 0)
            cont = float(art.get("contamination") or 100)
        except (TypeError, ValueError):
            comp, cont = 0.0, 100.0
        try:
            busco_c = float(art.get("busco_complete") or 0)
        except (TypeError, ValueError):
            busco_c = 0.0
        if comp >= 90 and cont <= 5:
            qclass = "high"
            hq += 1
        elif comp >= 50 and cont <= 10:
            qclass = "medium"
            mq += 1
        else:
            qclass = "low"
            lq += 1
        rows.append(
            f"{sid}\t{art.get('assembler', '')}\t{art.get('n_bins', '')}\t"
            f"{art.get('completeness', '')}\t{art.get('contamination', '')}\t"
            f"{busco_c}\t{qclass}\t{art.get('gtdb_summary', '')}"
        )
    (mag_dir / "mag_summary.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    summary_json = {
        "total_MAG": hq + mq + lq,
        "high_quality_MAG": hq,
        "medium_quality_MAG": mq,
        "low_quality_MAG": lq,
        "n_samples": len(per_sample),
        "refinement": "das_tool",
        "quality_tools": ["checkm2", "busco"],
    }
    (mag_dir / "mag_summary.json").write_text(
        __import__("json").dumps(summary_json, indent=2), encoding="utf-8"
    )
    result["mag_summary"] = str(mag_dir / "mag_summary.tsv")
    result["mag_summary_stats"] = summary_json
    return result
