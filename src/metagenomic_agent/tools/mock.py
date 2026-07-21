"""Shared mock outputs for dry-run without Docker/databases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_fastp(outdir: Path, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
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
                "q30_rate": 0.95,
                "gc_content": 0.45,
            },
        }
    }
    jpath = outdir / f"{sample_id}.fastp.json"
    jpath.write_text(json.dumps(payload, indent=2))
    (outdir / f"{sample_id}.fastp.html").write_text("<html><body>mock fastp</body></html>")
    (outdir / f"{sample_id}.clean_R1.fastq").write_text("@r1\nACGT\n+\nIIII\n")
    (outdir / f"{sample_id}.clean_R2.fastq").write_text("@r2\nACGT\n+\nIIII\n")
    return {
        "fastp_json": str(jpath),
        "fastp_html": str(outdir / f"{sample_id}.fastp.html"),
        "clean_r1": str(outdir / f"{sample_id}.clean_R1.fastq"),
        "clean_r2": str(outdir / f"{sample_id}.clean_R2.fastq"),
        "Q30": 95,
        "adapter_removed": True,
        "status": "PASS",
        "read_retention": 0.92,
        "host_fraction": 0.08,
    }


def write_taxonomy(outdir: Path, sample_id: str, tool: str) -> dict[str, Any]:
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
        "classification_rate": 0.72,
    }


def write_host_filter(outdir: Path, sample_id: str, upstream: dict[str, Any]) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    r1 = outdir / f"{sample_id}.nonhost_R1.fastq"
    r2 = outdir / f"{sample_id}.nonhost_R2.fastq"
    r1.write_text("@r1\nACGTACGT\n+\nIIIIIIII\n")
    r2.write_text("@r2\nACGTACGT\n+\nIIIIIIII\n")
    return {
        **upstream,
        "nonhost_r1": str(r1),
        "nonhost_r2": str(r2),
        "host_fraction": 0.08,
    }


def write_assembly(outdir: Path, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    contigs = outdir / f"{sample_id}.contigs.fa"
    contigs.write_text(f">{sample_id}_contig_1\n{'ATGC' * 200}\n")
    bins = outdir / "bins"
    bins.mkdir(exist_ok=True)
    (bins / f"{sample_id}.bin.1.fa").write_text(f">{sample_id}_bin1\n{'ATGC' * 500}\n")
    gtdb = outdir / f"{sample_id}.gtdbtk.summary.tsv"
    gtdb.write_text(
        "user_genome\tclassification\n"
        f"{sample_id}.bin.1\td__Bacteria;p__Bacteroidota;c__Bacteroidia;o__Bacteroidales;f__Bacteroidaceae;g__Bacteroides;s__Bacteroides_uniformis\n"
    )
    return {
        "contigs": str(contigs),
        "bins_dir": str(bins),
        "gtdb_summary": str(gtdb),
        "n_bins": 1,
    }


def write_functional(outdir: Path, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    profile = outdir / f"{sample_id}.functional_profile.tsv"
    profile.write_text(
        "feature\tabundance\tdatabase\n"
        "K00001\t120\tKEGG\n"
        "COG1234\t80\teggNOG\n"
        "GH13\t45\tCAZy\n"
        "ARO:3000010\t3\tCARD\n"
        "VFG0376\t2\tVFDB\n"
    )
    return {
        "functional_profile": str(profile),
        "databases": ["KEGG", "eggNOG", "CAZy", "CARD", "VFDB"],
        "n_features": 5,
    }
