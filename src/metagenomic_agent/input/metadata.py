"""Metadata helpers for case/control grouping and clinical/environmental covariates."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

_NUMERIC_HINTS = (
    "age",
    "bmi",
    "depth",
    "temp",
    "ph",
    "score",
    "days",
    "weight",
    "height",
    "fiber",
    "dose",
)


def load_sample_groups(metadata_path: str | Path | None) -> dict[str, str]:
    """Load sample_id -> group from TSV/CSV with columns sample_id,group."""
    meta = load_metadata_table(metadata_path)
    return {sid: row["group"] for sid, row in meta.items() if row.get("group")}


def load_metadata_table(metadata_path: str | Path | None) -> dict[str, dict[str, Any]]:
    """Load full metadata rows keyed by sample_id."""
    if not metadata_path:
        return {}
    path = Path(metadata_path)
    if not path.exists():
        raise FileNotFoundError(f"Metadata not found: {path}")
    rows: dict[str, dict[str, Any]] = {}
    with path.open(newline="") as f:
        sample = f.read(1024)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            sid = row.get("sample_id") or row.get("sample") or row.get("SampleID")
            if not sid:
                continue
            sid = sid.strip()
            cleaned = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
            group = cleaned.get("group") or cleaned.get("condition") or cleaned.get("Group")
            if group:
                cleaned["group"] = group
            rows[sid] = cleaned
    return rows


def extract_covariates(meta: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Numeric clinical/environmental covariates per sample."""
    out: dict[str, dict[str, float]] = {}
    for sid, row in meta.items():
        nums: dict[str, float] = {}
        for k, v in row.items():
            if k.lower() in {"sample_id", "sample", "group", "condition", "subject", "batch"}:
                continue
            try:
                nums[k] = float(v)
            except (TypeError, ValueError):
                continue
        if nums:
            out[sid] = nums
    return out


def extract_batch(
    meta: dict[str, dict[str, Any]], samples: list[dict[str, Any]] | None = None
) -> dict[str, str]:
    batch: dict[str, str] = {}
    for sid, row in meta.items():
        b = row.get("batch") or row.get("Batch") or row.get("plate")
        if b:
            batch[sid] = str(b)
    for s in samples or []:
        sid = s.get("sample_id")
        if sid and s.get("batch") and sid not in batch:
            batch[sid] = str(s["batch"])
    return batch


def extract_subject(meta: dict[str, dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for sid, row in meta.items():
        sub = row.get("subject") or row.get("Subject") or row.get("patient_id")
        if sub:
            out[sid] = str(sub)
    return out


def apply_groups(samples: list[dict[str, Any]], groups: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for s in samples:
        item = dict(s)
        if s["sample_id"] in groups:
            item["group"] = groups[s["sample_id"]]
        out.append(item)
    return out
