"""Summary-driven pipeline context — statistical metadata only, never raw sequences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def fasta_assembly_stats(path: str | Path | None, *, max_contigs: int = 500_000) -> dict[str, Any] | None:
    """Stream contig *lengths* only (discard bases). Computes N50, total bp, n_contigs."""
    if not path:
        return None
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    lengths: list[int] = []
    cur = 0
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith(">"):
                    if cur > 0:
                        lengths.append(cur)
                        if len(lengths) >= max_contigs:
                            break
                    cur = 0
                else:
                    # count bases without retaining the sequence string
                    cur += len(line.strip())
            else:
                if cur > 0 and len(lengths) < max_contigs:
                    lengths.append(cur)
    except OSError:
        return None
    if not lengths:
        return None
    lengths.sort(reverse=True)
    total = sum(lengths)
    half = total / 2.0
    cum = 0
    n50 = lengths[-1]
    for L in lengths:
        cum += L
        if cum >= half:
            n50 = L
            break
    return {
        "n_contigs": len(lengths),
        "total_bp": total,
        "n50": n50,
        "max_contig": lengths[0],
        "source": str(p),
        "note": "lengths_only_no_sequence_in_context",
    }


def _reads_from_fastp_json(path: str | None) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        before = data.get("summary", {}).get("before_filtering") or {}
        after = data.get("summary", {}).get("after_filtering") or {}
        return {
            "reads_before": before.get("total_reads"),
            "reads_after": after.get("total_reads"),
            "bases_before": before.get("total_bases"),
            "bases_after": after.get("total_bases"),
            "q30_rate_after": after.get("q30_rate"),
        }
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _qc_sample_summary(sid: str, art: dict[str, Any]) -> dict[str, Any]:
    reads = _reads_from_fastp_json(art.get("fastp_json"))
    return {
        "sample_id": sid,
        "Q30": art.get("Q30"),
        "read_retention": art.get("read_retention"),
        "host_fraction": art.get("host_fraction"),
        "status": art.get("status"),
        **reads,
        # paths kept as provenance pointers only — never sequence content
        "paths": {
            k: art.get(k)
            for k in ("fastp_json", "clean_r1", "clean_r2", "nonhost_r1", "nonhost_r2")
            if art.get(k)
        },
    }


def _tax_sample_summary(sid: str, art: dict[str, Any]) -> dict[str, Any]:
    top = art.get("top_genera") or []
    return {
        "sample_id": sid,
        "top_genera": top[:10],
        "classification_rate": art.get("classification_rate"),
        "tool": art.get("tool") or art.get("primary_tool"),
        "paths": {
            k: art.get(k)
            for k in ("kraken2_abundance", "metaphlan_abundance")
            if art.get(k)
        },
    }


def _asm_sample_summary(sid: str, art: dict[str, Any]) -> dict[str, Any]:
    contig_path = art.get("contigs")
    n50_stats = fasta_assembly_stats(contig_path)
    return {
        "sample_id": sid,
        "assembler": art.get("assembler"),
        "n_bins": art.get("n_bins"),
        "completeness": art.get("completeness"),
        "contamination": art.get("contamination"),
        "gtdb_summary": art.get("gtdb_summary"),
        "assembly": n50_stats,
        "paths": {k: art.get(k) for k in ("contigs", "checkm2", "bins_dir") if art.get(k)},
    }


def build_pipeline_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Aggregate run-level statistical metadata for LLM context & provenance."""
    arts = state.get("artifacts") or {}
    qc = arts.get("qc_host") or {}
    tax = arts.get("taxonomy") or {}
    asm = arts.get("assembly") or {}
    stats = arts.get("statistics") or state.get("statistics") or {}

    qc_rows = [_qc_sample_summary(sid, v) for sid, v in qc.items()]
    tax_rows = [_tax_sample_summary(sid, v) for sid, v in tax.items()]
    asm_rows = [_asm_sample_summary(sid, v) for sid, v in asm.items()]

    biomarkers = []
    for b in stats.get("biomarker_list") or []:
        biomarkers.append(
            {
                "genus": b.get("genus"),
                "direction": b.get("direction"),
                "p_value": b.get("p_value"),
                "q_value": b.get("q_value"),
                "log2fc": b.get("log2fc"),
            }
        )

    summary = {
        "policy": "summary_driven_no_raw_sequences",
        "run_id": state.get("run_id"),
        "mode": state.get("mode"),
        "n_samples": len(state.get("samples") or []),
        "qc": {
            "n_samples": len(qc_rows),
            "samples": qc_rows,
            "mean_Q30": _mean([r.get("Q30") for r in qc_rows]),
            "mean_read_retention": _mean([r.get("read_retention") for r in qc_rows]),
        },
        "taxonomy": {
            "n_samples": len(tax_rows),
            "samples": tax_rows,
            "mean_classification_rate": _mean([r.get("classification_rate") for r in tax_rows]),
        },
        "assembly_mags": {
            "n_samples": len(asm_rows),
            "samples": asm_rows,
            "mean_completeness": _mean([r.get("completeness") for r in asm_rows]),
            "mean_contamination": _mean([r.get("contamination") for r in asm_rows]),
            "mean_n50": _mean(
                [(r.get("assembly") or {}).get("n50") for r in asm_rows if r.get("assembly")]
            ),
        },
        "statistics": {
            "n_biomarkers": len(biomarkers),
            "biomarkers": biomarkers[:20],
            "methods": stats.get("methods") or [],
        },
        "dag_status": [
            {"id": n.get("id"), "agent": n.get("agent"), "status": n.get("status"), "tools": n.get("tools")}
            for n in (state.get("dag") or [])
        ],
        "errors_n": len(arts.get("errors") or []),
        "self_heal_actions": arts.get("self_heal_actions") or [],
    }
    return summary


def llm_context_from_summary(summary: dict[str, Any], *, max_chars: int = 12_000) -> str:
    """Compact JSON string safe for LLM prompts (metadata only)."""
    compact = {
        "policy": summary.get("policy"),
        "run_id": summary.get("run_id"),
        "mode": summary.get("mode"),
        "n_samples": summary.get("n_samples"),
        "qc": {
            "mean_Q30": (summary.get("qc") or {}).get("mean_Q30"),
            "mean_read_retention": (summary.get("qc") or {}).get("mean_read_retention"),
            "samples": [
                {
                    "sample_id": s.get("sample_id"),
                    "Q30": s.get("Q30"),
                    "read_retention": s.get("read_retention"),
                    "host_fraction": s.get("host_fraction"),
                    "reads_before": s.get("reads_before"),
                    "reads_after": s.get("reads_after"),
                }
                for s in ((summary.get("qc") or {}).get("samples") or [])
            ],
        },
        "taxonomy": {
            "mean_classification_rate": (summary.get("taxonomy") or {}).get("mean_classification_rate"),
            "samples": [
                {
                    "sample_id": s.get("sample_id"),
                    "top_genera": s.get("top_genera"),
                    "classification_rate": s.get("classification_rate"),
                }
                for s in ((summary.get("taxonomy") or {}).get("samples") or [])
            ],
        },
        "assembly_mags": {
            "mean_completeness": (summary.get("assembly_mags") or {}).get("mean_completeness"),
            "mean_contamination": (summary.get("assembly_mags") or {}).get("mean_contamination"),
            "mean_n50": (summary.get("assembly_mags") or {}).get("mean_n50"),
            "samples": [
                {
                    "sample_id": s.get("sample_id"),
                    "n_bins": s.get("n_bins"),
                    "completeness": s.get("completeness"),
                    "contamination": s.get("contamination"),
                    "n50": (s.get("assembly") or {}).get("n50"),
                    "n_contigs": (s.get("assembly") or {}).get("n_contigs"),
                }
                for s in ((summary.get("assembly_mags") or {}).get("samples") or [])
            ],
        },
        "statistics": summary.get("statistics"),
        "dag_status": summary.get("dag_status"),
        "self_heal_actions": summary.get("self_heal_actions"),
    }
    text = json.dumps(compact, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…[truncated]"
    return text


def get_llm_context(state: dict[str, Any], *, max_chars: int = 12_000) -> str:
    """Prefer cached pipeline_summary; rebuild if missing."""
    arts = state.get("artifacts") or {}
    summary = arts.get("pipeline_summary")
    if not summary:
        summary = build_pipeline_summary(state)
    cached = arts.get("llm_context")
    if isinstance(cached, str) and cached:
        return cached[:max_chars] if len(cached) > max_chars else cached
    return llm_context_from_summary(summary, max_chars=max_chars)


def write_pipeline_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Write summary JSON/MD under outdir/context/ and return summary dict."""
    summary = build_pipeline_summary(state)
    llm_ctx = llm_context_from_summary(summary)
    out = Path(state["outdir"]) / "context"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pipeline_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "llm_context.json").write_text(llm_ctx, encoding="utf-8")
    lines = [
        "# Pipeline summary (metadata only)",
        "",
        f"- run_id: `{summary.get('run_id')}`",
        f"- samples: {summary.get('n_samples')}",
        f"- mean Q30: {(summary.get('qc') or {}).get('mean_Q30')}",
        f"- mean read retention: {(summary.get('qc') or {}).get('mean_read_retention')}",
        f"- mean classification rate: {(summary.get('taxonomy') or {}).get('mean_classification_rate')}",
        f"- mean MAG completeness: {(summary.get('assembly_mags') or {}).get('mean_completeness')}",
        f"- mean N50: {(summary.get('assembly_mags') or {}).get('mean_n50')}",
        "",
        "Raw FASTQ/BAM/FASTA sequences are **not** loaded into the agent context window.",
        "",
    ]
    (out / "pipeline_summary.md").write_text("\n".join(lines), encoding="utf-8")
    summary["path"] = str(out / "pipeline_summary.json")
    summary["llm_context_path"] = str(out / "llm_context.json")
    return {**summary, "_llm_context": llm_ctx}


def _mean(vals: list[Any]) -> float | None:
    nums = [float(v) for v in vals if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)
