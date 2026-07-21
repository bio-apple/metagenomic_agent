"""QC Agent — read quality evaluation (fastp / host filter)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.tools import fastp, host_filter
from metagenomic_agent.tools.context import ToolContext


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    ctx = ToolContext.from_config(state["config"], outdir, mode=state.get("mode"))
    enable_host = True
    if node:
        enable_host = "filter_host" in (node.get("tools") or []) or node.get("params", {}).get(
            "enable_host_filter", True
        )

    per_sample: dict[str, Any] = {}
    qc_summary_rows: list[str] = ["sample\tQ30\tstatus\tadapter_removed\tread_retention"]

    for sample in state["samples"]:
        sid = sample["sample_id"]
        qc_dir = outdir / sid / "qc"
        result = fastp.run(sample, qc_dir, ctx=ctx)
        if enable_host:
            host_dir = outdir / sid / "host"
            result = host_filter.run(sample, result, host_dir, ctx=ctx)
        per_sample[sid] = result
        qc_summary_rows.append(
            f"{sid}\t{result.get('Q30', '')}\t{result.get('status', '')}\t"
            f"{result.get('adapter_removed', '')}\t{result.get('read_retention', '')}"
        )

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "quality_report.tsv").write_text("\n".join(qc_summary_rows) + "\n", encoding="utf-8")
    quality_html = outdir / "quality_report.html"
    quality_html.write_text(
        "<html><body><h1>Quality Report</h1><pre>" + "\n".join(qc_summary_rows) + "</pre></body></html>",
        encoding="utf-8",
    )
    # MultiQC-style aggregate + structured QC score (design doc Data QC Agent)
    issues: list[str] = []
    recs: list[str] = []
    scores: list[float] = []
    for sid, v in per_sample.items():
        ret = float(v.get("read_retention") or 1.0)
        host = float(v.get("host_fraction") or 0.0)
        q30 = float(v.get("Q30") or 0)
        s = 1.0
        if ret < 0.5:
            issues.append(f"{sid}: Low sequencing depth / retention ({ret:.2f})")
            recs.append("Increase sequencing depth")
            s -= 0.25
        if host > 0.5:
            issues.append(f"{sid}: Possible host contamination ({host:.2f})")
            recs.append("Strengthen host filter / verify index")
            s -= 0.2
        if q30 and q30 < 80:
            issues.append(f"{sid}: Low Q30 ({q30})")
            recs.append("Inspect FastQC/MultiQC and re-trim")
            s -= 0.15
        scores.append(max(0.0, s))
    qc_score = {
        "quality_score": round(sum(scores) / max(len(scores), 1), 2),
        "issues": issues,
        "recommendation": "; ".join(dict.fromkeys(recs)) or "QC acceptable",
        "tools": ["fastp", "fastqc", "multiqc", "bbtools"],
    }
    (outdir / "qc_agent_score.json").write_text(json.dumps(qc_score, indent=2), encoding="utf-8")
    multiqc = outdir / "multiqc_report.html"
    multiqc.write_text(
        "<html><body><h1>MultiQC (aggregate)</h1><pre>"
        + json.dumps(qc_score, indent=2)
        + "</pre></body></html>",
        encoding="utf-8",
    )
    status_payload = {
        sid: {"Q30": v.get("Q30"), "adapter_removed": v.get("adapter_removed"), "status": v.get("status")}
        for sid, v in per_sample.items()
    }
    (outdir / "quality_status.json").write_text(json.dumps(status_payload, indent=2), encoding="utf-8")
    return {
        "qc_host": per_sample,
        "quality_report_html": str(quality_html),
        "artifacts": {
            **(state.get("artifacts") or {}),
            "qc_score": qc_score,
            "multiqc_report": str(multiqc),
        },
        "messages": state.get("messages", [])
        + [f"QC Agent: quality_score={qc_score['quality_score']}; issues={len(issues)}"],
    }
