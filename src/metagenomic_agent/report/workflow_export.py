"""Post-run reproducible workflow export (.nf / .smk) with seeds and config snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from metagenomic_agent import __version__


def resolve_run_seed(state: dict[str, Any]) -> int:
    cfg = (state.get("config") or {}).get("reproducibility") or {}
    if cfg.get("seed") is not None:
        return int(cfg["seed"])
    existing = (state.get("artifacts") or {}).get("run_seed")
    if existing is not None:
        return int(existing)
    rid = str(state.get("run_id") or "0")
    return int(hashlib.sha256(rid.encode()).hexdigest()[:8], 16) % (2**31 - 1)


def export_executed_workflows(state: dict[str, Any]) -> dict[str, str]:
    """Write peer-reviewable Nextflow/Snakemake from the *executed* DAG + seed."""
    outdir = Path(state["outdir"]) / "workflow"
    outdir.mkdir(parents=True, exist_ok=True)
    seed = resolve_run_seed(state)
    dag = state.get("dag") or []
    cfg = state.get("config") or {}
    query = (state.get("user_query") or "").replace("'", "\\'")[:200]
    input_path = state.get("input_path") or ""
    results = state.get("outdir") or "results"
    mode = state.get("mode") or "mock"
    threads = (cfg.get("linux") or {}).get("threads") or (cfg.get("docker") or {}).get("threads") or 8

    # --- Nextflow ---
    nf: list[str] = [
        "#!/usr/bin/env nextflow",
        f"// Reproducible export by metagenomic-agent v{__version__}",
        f"// run_id={state.get('run_id')} seed={seed}",
        f"// query: {query}",
        "nextflow.enable.dsl=2",
        "",
        f"params.input = '{input_path}'",
        f"params.outdir = '{results}'",
        f"params.mode = '{mode}'",
        f"params.seed = {seed}",
        f"params.threads = {threads}",
        f"params.query = '{query}'",
        "",
        "process AGENT_ORCHESTRATE {",
        "  tag \"meta-agent\"",
        "  publishDir params.outdir, mode: 'copy'",
        "  cpus params.threads",
        "",
        "  output:",
        "    path 'final_report.html', emit: report",
        "    path 'reproducibility/run_manifest.json', emit: manifest",
        "",
        "  script:",
        "  \"\"\"",
        "  meta-agent run --input ${params.input} --outdir ${params.outdir} --mode ${params.mode} --query '${params.query}' --yes",
        "  \"\"\"",
        "}",
        "",
    ]
    for n in dag:
        nid = n.get("id") or "step"
        agent = n.get("agent") or ""
        tools = ",".join(n.get("tools") or [])
        status = n.get("status") or "unknown"
        params = json.dumps(n.get("params") or {}, ensure_ascii=False)
        nf.append(f"// executed_node id={nid} agent={agent} status={status} tools=[{tools}]")
        nf.append(f"// params={params}")
    nf.append("")
    nf.append("workflow {")
    nf.append("  AGENT_ORCHESTRATE()")
    nf.append("}")
    nf.append("")

    # --- Snakemake ---
    smk: list[str] = [
        f"# Reproducible Snakemake export — metagenomic-agent v{__version__}",
        f"# run_id={state.get('run_id')} seed={seed}",
        f"# query: {query}",
        "",
        f'SEED = {seed}',
        f'THREADS = {threads}',
        f'INPUT = "{input_path}"',
        f'OUTDIR = "{results}"',
        f'MODE = "{mode}"',
        f'QUERY = "{query}"',
        "",
        "rule all:",
        '    input: f"{OUTDIR}/final_report.html", f"{OUTDIR}/reproducibility/run_manifest.json"',
        "",
        "rule agent_orchestrate:",
        '    output: f"{OUTDIR}/final_report.html", f"{OUTDIR}/reproducibility/run_manifest.json"',
        "    params:",
        "        seed=SEED,",
        "        query=QUERY,",
        "    threads: THREADS",
        "    shell:",
        '        "meta-agent run --input {INPUT} --outdir {OUTDIR} --mode {MODE} "',
        '        "--query {params.query:q} --yes"',
        "",
    ]
    for n in dag:
        nid = str(n.get("id") or "step").replace("-", "_")
        agent = n.get("agent") or ""
        tools = n.get("tools") or []
        status = n.get("status") or "unknown"
        smk.append(f"# node {nid}: agent={agent} status={status} tools={tools}")
        smk.append(f"# rule _{nid}_provenance:")
        smk.append(f"#     # executed via agent={agent}; params={json.dumps(n.get('params') or {})}")
        smk.append("")

    nf_path = outdir / "reproducible.nf"
    smk_path = outdir / "reproducible.smk"
    nf_path.write_text("\n".join(nf), encoding="utf-8")
    smk_path.write_text("\n".join(smk), encoding="utf-8")

    seeds = {
        "run_seed": seed,
        "run_id": state.get("run_id"),
        "agent_version": __version__,
        "numpy_seed_note": "Pass reproducibility.seed in config to pin; default derived from run_id.",
        "dag_node_seeds": {str(n.get("id")): seed for n in dag},
    }
    seeds_path = outdir / "seeds.json"
    seeds_path.write_text(json.dumps(seeds, indent=2), encoding="utf-8")

    # Config snapshot (full run config for peer review)
    snap_path = outdir / "config_snapshot.yaml"
    snap_path.write_text(
        yaml.safe_dump(
            {
                "agent_version": __version__,
                "run_id": state.get("run_id"),
                "seed": seed,
                "mode": mode,
                "input_path": input_path,
                "outdir": results,
                "user_query": state.get("user_query"),
                "config": cfg,
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    return {
        "nextflow": str(nf_path),
        "snakemake": str(smk_path),
        "seeds": str(seeds_path),
        "config_snapshot": str(snap_path),
        "run_seed": str(seed),
    }
