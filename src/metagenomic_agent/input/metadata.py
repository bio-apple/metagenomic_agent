"""Metadata helpers for case/control grouping."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def load_sample_groups(metadata_path: str | Path | None) -> dict[str, str]:
    """Load sample_id -> group from TSV/CSV with columns sample_id,group."""
    if not metadata_path:
        return {}
    path = Path(metadata_path)
    if not path.exists():
        raise FileNotFoundError(f"Metadata not found: {path}")
    groups: dict[str, str] = {}
    with path.open(newline="") as f:
        # sniff delimiter
        sample = f.read(1024)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            sid = row.get("sample_id") or row.get("sample") or row.get("SampleID")
            group = row.get("group") or row.get("condition") or row.get("Group")
            if sid and group:
                groups[sid.strip()] = group.strip()
    return groups


def apply_groups(samples: list[dict[str, Any]], groups: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for s in samples:
        item = dict(s)
        if s["sample_id"] in groups:
            item["group"] = groups[s["sample_id"]]
        out.append(item)
    return out
