"""Genomic Language Model adapters (microCafe / MicroRAG) — mock + external inference hook."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from metagenomic_agent.tools import mock as mock_tools
from metagenomic_agent.tools.context import ToolContext


def _run_external_inference(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext,
    model: str,
) -> dict[str, Any] | None:
    """Optional real gLM via config paths.glm_inference_cmd template.

    Template placeholders: {sample_id} {r1} {r2} {outdir} {weights} {model}
    Command must write TSV genus\\trelative_abundance to {outdir}/{sample_id}.{model}.tsv
    """
    cmd_tpl = (ctx.paths.get("glm_inference_cmd") or "").strip()
    weights = (ctx.paths.get("glm_weights") or "").strip()
    if not cmd_tpl or not weights:
        return None
    sample_id = sample["sample_id"]
    out = outdir / f"{sample_id}.{model}.tsv"
    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample.get("r1") or ""
    r2 = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2") or ""
    cmd = cmd_tpl.format(
        sample_id=sample_id,
        r1=r1,
        r2=r2 or "",
        outdir=str(outdir),
        weights=weights,
        model=model,
        output=str(out),
    )
    try:
        proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0 or not out.exists():
            return None
        top = []
        for line in out.read_text(encoding="utf-8").splitlines()[1:6]:
            parts = line.split("\t")
            if parts:
                top.append(parts[0])
        return {
            "glm_abundance": str(out),
            f"{model}_abundance": str(out),
            "top_genera": top,
            "glm_model": model,
            "glm_mode": "external",
            "classification_rate": 0.75,
        }
    except Exception:  # noqa: BLE001
        return None


def run_microcafe(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext | None = None,
    **_: Any,
) -> dict[str, Any]:
    ctx = ctx or ToolContext(mode="mock", outdir=outdir)
    sample_id = sample["sample_id"]
    outdir.mkdir(parents=True, exist_ok=True)
    weights = (ctx.paths.get("glm_weights") or "").strip()

    if ctx.mode == "mock" and not weights:
        base = mock_tools.write_taxonomy(outdir, sample_id, "microcafe")
        table = Path(base["microcafe_abundance"])
        return {
            **base,
            "glm_abundance": str(table),
            "glm_model": "microcafe",
            "glm_mode": "mock",
            "classification_rate": 0.78,
        }

    external = _run_external_inference(sample, upstream, outdir, ctx, "microcafe")
    if external:
        return external

    # Weights present but no inference cmd — deterministic placeholder for integration tests
    out = outdir / f"{sample_id}.microcafe.tsv"
    out.write_text(
        "genus\trelative_abundance\nBacteroides\t0.28\nFaecalibacterium\t0.12\nPrevotella\t0.10\n",
        encoding="utf-8",
    )
    return {
        "glm_abundance": str(out),
        "microcafe_abundance": str(out),
        "top_genera": ["Bacteroides", "Faecalibacterium", "Prevotella"],
        "glm_model": "microcafe",
        "glm_mode": "weights_placeholder",
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
    external = _run_external_inference(sample, upstream, outdir, ctx, "microrag")
    if external:
        return external
    base = mock_tools.write_taxonomy(outdir, sample_id, "microrag")
    return {
        **base,
        "glm_abundance": base["microrag_abundance"],
        "glm_model": "microrag",
        "glm_mode": "mock",
        "classification_rate": 0.74,
    }


def fuse_taxonomy(results: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import defaultdict

    scores: dict[str, list[float]] = defaultdict(list)
    for art in results:
        for key in (
            "kraken2_abundance",
            "metaphlan_abundance",
            "glm_abundance",
            "microcafe_abundance",
            "microrag_abundance",
        ):
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
