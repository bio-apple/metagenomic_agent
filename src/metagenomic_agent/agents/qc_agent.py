"""QC Agent — read quality evaluation (fastp / FastQC / MultiQC)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.tools import fastp, host_filter


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    mode = state["mode"]
    cfg = state["config"]
    image = cfg.get("docker", {}).get("image", "meta:latest")
    threads = int(cfg.get("docker", {}).get("threads", 8))
    host_index = cfg.get("paths", {}).get("host_index", "")
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
        result = fastp.run(sample, qc_dir, mode=mode, docker_image=image, threads=threads)
        if enable_host:
            host_dir = outdir / sid / "host"
            result = host_filter.run(
                sample, result, host_dir, mode=mode, docker_image=image, host_index=host_index, threads=threads
            )
        per_sample[sid] = result
        qc_summary_rows.append(
            f"{sid}\t{result.get('Q30', '')}\t{result.get('status', '')}\t"
            f"{result.get('adapter_removed', '')}\t{result.get('read_retention', '')}"
        )

    # Aggregate quality report
    report_dir = outdir
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "quality_report.tsv").write_text("\n".join(qc_summary_rows) + "\n", encoding="utf-8")
    quality_html = report_dir / "quality_report.html"
    quality_html.write_text(
        "<html><body><h1>Quality Report (MultiQC-style)</h1><pre>"
        + "\n".join(qc_summary_rows)
        + "</pre></body></html>",
        encoding="utf-8",
    )
    status_payload = {
        sid: {"Q30": v.get("Q30"), "adapter_removed": v.get("adapter_removed"), "status": v.get("status")}
        for sid, v in per_sample.items()
    }
    (report_dir / "quality_status.json").write_text(json.dumps(status_payload, indent=2), encoding="utf-8")

    return {"qc_host": per_sample, "quality_report_html": str(quality_html)}
