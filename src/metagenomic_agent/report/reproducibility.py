"""Reproducibility packaging: CWL fragment + Nextflow params for journal requirements."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent import __version__


def write_reproducibility_bundle(state: dict[str, Any]) -> dict[str, str]:
    outdir = Path(state["outdir"]) / "reproducibility"
    outdir.mkdir(parents=True, exist_ok=True)

    dag = state.get("dag") or []
    cfg = state.get("config") or {}
    manifest = {
        "software": "metagenomic-agent",
        "version": __version__,
        "run_id": state.get("run_id"),
        "mode": state.get("mode"),
        "query": state.get("user_query"),
        "input_path": state.get("input_path"),
        "metadata_path": state.get("metadata_path"),
        "playbooks": (state.get("artifacts") or {}).get("playbooks"),
        "routing": (state.get("artifacts") or {}).get("taxonomy_routing"),
        "contract_check": (state.get("artifacts") or {}).get("contract_check"),
        "self_heal_actions": (state.get("artifacts") or {}).get("self_heal_actions"),
        "dag": dag,
        "config": {
            "pipeline": cfg.get("pipeline"),
            "routing": cfg.get("routing"),
            "validation": cfg.get("validation"),
            "linux": {k: cfg.get("linux", {}).get(k) for k in ("threads", "memory_gb", "prefer_shm")},
            "docker": {"threads": (cfg.get("docker") or {}).get("threads")},
        },
    }
    manifest_path = outdir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Minimal CWL CommandLineTool wrapping the CLI (journal-friendly artifact)
    cwl = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "label": "metagenomic-agent",
        "baseCommand": ["meta-agent", "run"],
        "inputs": {
            "input": {"type": "Directory", "inputBinding": {"prefix": "--input"}},
            "outdir": {"type": "string", "default": "results", "inputBinding": {"prefix": "--outdir"}},
            "mode": {"type": "string", "default": state.get("mode") or "mock", "inputBinding": {"prefix": "--mode"}},
            "query": {
                "type": "string",
                "default": state.get("user_query") or "",
                "inputBinding": {"prefix": "--query"},
            },
            "yes": {"type": "boolean", "default": True, "inputBinding": {"prefix": "--yes"}},
        },
        "outputs": {
            "report": {"type": "File", "outputBinding": {"glob": "**/final_report.html"}},
            "manifest": {"type": "File", "outputBinding": {"glob": "**/run_manifest.json"}},
        },
        "requirements": [{"class": "DockerRequirement", "dockerPull": "python:3.11-slim"}],
        "hints": {"SoftwareRequirement": {"packages": [{"package": "metagenomic-agent", "version": [__version__]}]}},
    }
    cwl_path = outdir / "meta_agent.cwl"
    cwl_path.write_text(json.dumps(cwl, indent=2), encoding="utf-8")

    # Nextflow params already written elsewhere; add a companion job script
    nf_params = outdir / "nextflow_params.json"
    nf_params.write_text(
        json.dumps(
            {
                "input": state.get("input_path"),
                "outdir": state.get("outdir"),
                "mode": state.get("mode"),
                "query": state.get("user_query"),
                "agent_version": __version__,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    readme = outdir / "README.md"
    readme.write_text(
        "# Reproducibility bundle\n\n"
        f"- Agent version: `{__version__}`\n"
        f"- Run id: `{state.get('run_id')}`\n"
        "- `run_manifest.json`: full DAG, config subset, contracts, routing\n"
        "- `meta_agent.cwl`: CWL CommandLineTool wrapper for the CLI\n"
        "- `nextflow_params.json`: parameters for Nextflow handoff\n"
        "- Also see `../report/reproduce.sh` and `../logs/events.jsonl`\n",
        encoding="utf-8",
    )
    return {
        "manifest": str(manifest_path),
        "cwl": str(cwl_path),
        "nextflow_params": str(nf_params),
        "readme": str(readme),
    }
