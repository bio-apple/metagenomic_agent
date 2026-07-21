"""Assembly / long-step checkpoints — reuse MEGAHIT/SPAdes contigs on resume."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTIG_CANDIDATES = (
    "final.contigs.fa",
    "contigs.fa",
    "contigs.fasta",
    "scaffolds.fasta",
)


def find_contigs(asm_dir: Path) -> Path | None:
    for name in CONTIG_CANDIDATES:
        p = asm_dir / name
        if p.exists() and p.stat().st_size > 0:
            return p
    # MEGAHIT intermediate
    intermediate = asm_dir / "intermediate_contigs" / "final.contigs"
    if intermediate.exists() and intermediate.stat().st_size > 0:
        return intermediate
    return None


def load_assembly_checkpoint(asm_dir: Path, sid: str) -> dict[str, Any] | None:
    """Return artifact dict if a durable assembly checkpoint exists."""
    contigs = find_contigs(asm_dir)
    if not contigs:
        return None
    meta_path = asm_dir / "checkpoint.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    return {
        "sample_id": sid,
        "contigs": str(contigs),
        "assembler": meta.get("assembler") or "checkpoint",
        "status": "cached_checkpoint",
        "checkpoint": True,
        "checkpoint_path": str(meta_path) if meta_path.exists() else str(contigs),
    }


def write_assembly_checkpoint(asm_dir: Path, artifact: dict[str, Any]) -> Path:
    asm_dir.mkdir(parents=True, exist_ok=True)
    path = asm_dir / "checkpoint.json"
    payload = {
        "assembler": artifact.get("assembler"),
        "contigs": artifact.get("contigs"),
        "n_bins": artifact.get("n_bins"),
        "completeness": artifact.get("completeness"),
        "contamination": artifact.get("contamination"),
        "status": artifact.get("status") or "ok",
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def list_assembly_checkpoints(outdir: Path, sample_ids: list[str]) -> dict[str, str]:
    hits = {}
    for sid in sample_ids:
        cp = load_assembly_checkpoint(outdir / sid / "assembly", sid)
        if cp:
            hits[sid] = cp["contigs"]
    return hits
