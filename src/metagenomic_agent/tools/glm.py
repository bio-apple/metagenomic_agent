"""Genomic Language Model adapters (microCafe / MicroRAG) — mock-capable first-class skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.context import ToolContext


def run_microcafe(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Long-read friendly gLM taxonomy. Real weights optional via config paths.glm_weights."""
    ctx = ctx or ToolContext(mode="mock", outdir=outdir)
    sample_id = sample["sample_id"]
    outdir.mkdir(parents=True, exist_ok=True)
    weights = (ctx.paths.get("glm_weights") or "").strip()

    if ctx.mode == "mock" or not weights:
        base = mock_tools.write_taxonomy(outdir, sample_id, "microcafe")
        # Emphasize long-read speed narrative in metadata
        table = Path(base["microcafe_abundance"])
        return {
            **base,
            "glm_abundance": str(table),
            "glm_model": "microcafe",
            "glm_mode": "mock" if ctx.mode == "mock" or not weights else "weights",
            "classification_rate": 0.78,
        }

    # Placeholder for real inference entrypoint
    out = outdir / f"{sample_id}.microcafe.tsv"
    out.write_text("genus\trelative_abundance\nBacteroides\t0.3\n", encoding="utf-8")
    return {
        "glm_abundance": str(out),
        "microcafe_abundance": str(out),
        "top_genera": ["Bacteroides"],
        "glm_model": "microcafe",
        "classification_rate": 0.7,
    }


def run_microrag(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext | None = None,
    **_: Any,
) -> dict[str, Any]:
    ctx = ctx or ToolContext(mode="mock", outdir=outdir)
    sample_id = sample["sample_id"]
    outdir.mkdir(parents=True, exist_ok=True)
    base = mock_tools.write_taxonomy(outdir, sample_id, "microrag")
    return {
        **base,
        "glm_abundance": base["microrag_abundance"],
        "glm_model": "microrag",
        "classification_rate": 0.74,
    }


def fuse_taxonomy(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-validate / fuse multi-tool taxonomy by averaging shared genera."""
    from collections import defaultdict

    scores: dict[str, list[float]] = defaultdict(list)
    for art in results:
        for key in ("kraken2_abundance", "metaphlan_abundance", "glm_abundance", "microcafe_abundance", "microrag_abundance"):
            path = art.get(key)
            if not path or not Path(path).exists():
                continue
            for line in Path(path).read_text().splitlines()[1:]:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    try:
                        scores[parts[0]].append(float(parts[1]))
                    except ValueError:
                        pass
    fused = {g: sum(vs) / len(vs) for g, vs in scores.items() if vs}
    top = sorted(fused.items(), key=lambda x: -x[1])[:8]
    return {
        "fused_genera": [{"genus": g, "abundance": a} for g, a in top],
        "top_genera": [g for g, _ in top[:5]],
        "n_tools_fused": len(results),
        "classification_rate": max((r.get("classification_rate") or 0) for r in results) if results else 0,
    }
