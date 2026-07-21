"""Mock tool outputs for dry-run / demo without Docker databases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_mock_fastp(outdir: Path, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    html = outdir / f"{sample_id}.fastp.html"
    jpath = outdir / f"{sample_id}.fastp.json"
    tsv = outdir / f"{sample_id}.fastp.tsv"
    payload = {
        "summary": {
            "before_filtering": {
                "total_reads": 1_000_000,
                "total_bases": 150_000_000,
                "q20_rate": 0.95,
                "q30_rate": 0.88,
                "gc_content": 0.45,
            },
            "after_filtering": {
                "total_reads": 920_000,
                "total_bases": 138_000_000,
                "q20_rate": 0.98,
                "q30_rate": 0.92,
                "gc_content": 0.45,
            },
        }
    }
    jpath.write_text(json.dumps(payload, indent=2))
    html.write_text("<html><body>mock fastp</body></html>")
    tsv.write_text(
        "SampleID\tTotal_reads(Raw)\tTotal_reads(clean)\n"
        f"{sample_id}\t1000000\t920000\n"
    )
    (outdir / f"{sample_id}.clean_R1.fastq").write_text("@r1\nACGT\n+\nIIII\n")
    (outdir / f"{sample_id}.clean_R2.fastq").write_text("@r2\nACGT\n+\nIIII\n")
    return {
        "fastp_json": str(jpath),
        "fastp_html": str(html),
        "fastp_tsv": str(tsv),
        "clean_r1": str(outdir / f"{sample_id}.clean_R1.fastq"),
        "clean_r2": str(outdir / f"{sample_id}.clean_R2.fastq"),
        "read_retention": 0.92,
        "host_fraction": 0.08,
    }


def write_mock_host_filter(outdir: Path, sample_id: str, upstream: dict[str, Any]) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    nonhost_r1 = outdir / f"{sample_id}.nonhost_R1.fastq"
    nonhost_r2 = outdir / f"{sample_id}.nonhost_R2.fastq"
    nonhost_r1.write_text("@r1\nACGTACGT\n+\nIIIIIIII\n")
    nonhost_r2.write_text("@r2\nACGTACGT\n+\nIIIIIIII\n")
    stats = outdir / f"{sample_id}.host_filter.tsv"
    stats.write_text("sample\thost_fraction\tnonhost_reads\n" f"{sample_id}\t0.08\t846400\n")
    return {
        **upstream,
        "nonhost_r1": str(nonhost_r1),
        "nonhost_r2": str(nonhost_r2),
        "host_filter_tsv": str(stats),
        "host_fraction": 0.08,
    }


def write_mock_taxonomy(outdir: Path, sample_id: str, tool: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    table = outdir / f"{sample_id}.{tool}.abundance.tsv"
    rows = [
        ("Bacteroides", 0.28),
        ("Faecalibacterium", 0.18),
        ("Prevotella", 0.12),
        ("Bifidobacterium", 0.09),
        ("Roseburia", 0.06),
        ("Escherichia", 0.04),
        ("Other", 0.23),
    ]
    table.write_text("genus\trelative_abundance\n" + "".join(f"{g}\t{a}\n" for g, a in rows))
    report = outdir / f"{sample_id}.{tool}.report.txt"
    report.write_text(f"mock {tool} report for {sample_id}\n")
    return {
        f"{tool}_abundance": str(table),
        f"{tool}_report": str(report),
        "top_genera": [g for g, _ in rows[:5]],
    }


def write_mock_functional(outdir: Path, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{sample_id}.diamond.tsv"
    path.write_text(
        "qseqid\tsseqid\tpident\tKO\tdescription\n"
        "gene1\tUniRef90_X\t95.0\tK00001\talcohol dehydrogenase\n"
        "gene2\tUniRef90_Y\t90.0\tK00626\tacetyl-CoA C-acetyltransferase\n"
    )
    return {"diamond_tsv": str(path), "n_hits": 2}
