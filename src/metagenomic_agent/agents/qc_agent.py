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
    status_payload = {
        sid: {"Q30": v.get("Q30"), "adapter_removed": v.get("adapter_removed"), "status": v.get("status")}
        for sid, v in per_sample.items()
    }
    (outdir / "quality_status.json").write_text(json.dumps(status_payload, indent=2), encoding="utf-8")
    return {"qc_host": per_sample, "quality_report_html": str(quality_html)}
