"""Specialized bioagents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools import wrappers


def _sample_outdir(base: Path, sample_id: str, step: str) -> Path:
    d = base / sample_id / step
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_qc_host(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    mode = state["mode"]
    cfg = state["config"]
    image = cfg.get("docker", {}).get("image", "meta:latest")
    threads = int(cfg.get("docker", {}).get("threads", 8))
    host_index = cfg.get("paths", {}).get("host_index", "")
    artifacts: dict[str, Any] = {"qc_host": {}}

    for sample in state["samples"]:
        sid = sample["sample_id"]
        qc_dir = _sample_outdir(outdir, sid, "qc")
        result = wrappers.run_fastp(sample, qc_dir, mode, image, threads=threads)
        if node.get("params", {}).get("enable_host_filter", True) and "filter_host" in node.get("tools", []):
            host_dir = _sample_outdir(outdir, sid, "host")
            result = wrappers.run_host_filter(
                sample, result, host_dir, mode, image, host_index, threads=threads
            )
        artifacts["qc_host"][sid] = result
    return artifacts


def run_taxonomy(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    mode = state["mode"]
    cfg = state["config"]
    image = cfg.get("docker", {}).get("image", "meta:latest")
    kraken_db = cfg.get("paths", {}).get("kraken2_db", "")
    tools = node.get("params", {}).get("tools") or node.get("tools") or ["kraken2"]
    confidence = float(node.get("params", {}).get("confidence", 0.05))
    artifacts: dict[str, Any] = {"taxonomy": {}}
    qc_arts = state.get("artifacts", {}).get("qc_host", {})

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        tax_dir = _sample_outdir(outdir, sid, "taxonomy")
        sample_art: dict[str, Any] = {"top_genera": []}
        if "kraken2" in tools:
            k = wrappers.run_kraken2(
                sample,
                upstream,
                tax_dir,
                mode,
                image,
                kraken_db,
                read_length=sample.get("read_length_est", 150),
                confidence=confidence,
            )
            sample_art.update(k)
            sample_art["top_genera"] = list(dict.fromkeys(sample_art.get("top_genera", []) + k.get("top_genera", [])))
        if "metaphlan" in tools:
            m = wrappers.run_metaphlan(sample, upstream, tax_dir, mode, image)
            sample_art.update(m)
            sample_art["top_genera"] = list(
                dict.fromkeys(sample_art.get("top_genera", []) + m.get("top_genera", []))
            )
        artifacts["taxonomy"][sid] = sample_art
    return artifacts


def run_functional(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    mode = state["mode"]
    cfg = state["config"]
    image = cfg.get("docker", {}).get("image", "meta:latest")
    artifacts: dict[str, Any] = {"functional": {}}
    qc_arts = state.get("artifacts", {}).get("qc_host", {})

    for sample in state["samples"]:
        sid = sample["sample_id"]
        upstream = qc_arts.get(sid, {})
        fun_dir = _sample_outdir(outdir, sid, "functional")
        if "humann4" in node.get("tools", []):
            # HUMAnN4 not wired in MVP; fall back to diamond mock/docker
            pass
        artifacts["functional"][sid] = wrappers.run_diamond(sample, upstream, fun_dir, mode, image)
    return artifacts


def run_assembly_stub(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    return {"assembly": {"skipped": True, "reason": "MVP stub — enable later"}}


def run_genomic_lm_stub(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    return {"genomic_lm": {"skipped": True, "reason": "MVP stub — microCafe/MicroRAG not wired"}}


def run_stats_stub(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    return {"stats": {"skipped": True, "reason": "MVP stub — DESeq2/Maaslin2 not wired"}}


AGENT_REGISTRY = {
    "qc_host": run_qc_host,
    "taxonomy": run_taxonomy,
    "functional": run_functional,
    "assembly": run_assembly_stub,
    "genomic_lm": run_genomic_lm_stub,
    "stats": run_stats_stub,
}
