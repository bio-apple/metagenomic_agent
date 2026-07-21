"""Reproducibility packaging: CWL + Nextflow/Snakemake + seeds + config snapshot + summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent import __version__
from metagenomic_agent.report.workflow_export import export_executed_workflows, resolve_run_seed


def write_reproducibility_bundle(state: dict[str, Any]) -> dict[str, str]:
    outdir = Path(state["outdir"]) / "reproducibility"
    outdir.mkdir(parents=True, exist_ok=True)

    seed = resolve_run_seed(state)
    dag = state.get("dag") or []
    cfg = state.get("config") or {}
    arts = state.get("artifacts") or {}
    summary = arts.get("pipeline_summary") or {}

    # Post-run executable workflow files
    wf = export_executed_workflows(state)

    manifest = {
        "software": "metagenomic-agent",
        "version": __version__,
        "run_id": state.get("run_id"),
        "run_seed": seed,
        "mode": state.get("mode"),
        "query": state.get("user_query"),
        "input_path": state.get("input_path"),
        "metadata_path": state.get("metadata_path"),
        "playbooks": arts.get("playbooks"),
        "routing": arts.get("taxonomy_routing"),
        "contract_check": arts.get("contract_check"),
        "self_heal_actions": arts.get("self_heal_actions"),
        "pipeline_summary_ref": summary.get("path") or str(Path(state["outdir"]) / "context" / "pipeline_summary.json"),
        "dag": dag,
        "config": {
            "pipeline": cfg.get("pipeline"),
            "routing": cfg.get("routing"),
            "validation": cfg.get("validation"),
            "reproducibility": cfg.get("reproducibility"),
            "sandbox": {
                k: (cfg.get("sandbox") or {}).get(k)
                for k in ("backend", "prefer_container", "platform", "allow_mock_fallback")
            },
            "linux": {k: (cfg.get("linux") or {}).get(k) for k in ("threads", "memory_gb", "prefer_shm")},
            "docker": {"threads": (cfg.get("docker") or {}).get("threads"), "platform": (cfg.get("docker") or {}).get("platform")},
        },
        "workflows": wf,
    }
    manifest_path = outdir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copy seed pointer into reproducibility/
    seeds_copy = outdir / "seeds.json"
    seeds_src = Path(wf["seeds"])
    if seeds_src.exists():
        seeds_copy.write_text(seeds_src.read_text(encoding="utf-8"), encoding="utf-8")

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
            "workflow_nf": {"type": "File", "outputBinding": {"glob": "**/reproducible.nf"}},
            "workflow_smk": {"type": "File", "outputBinding": {"glob": "**/reproducible.smk"}},
        },
        "requirements": [{"class": "DockerRequirement", "dockerPull": "python:3.11-slim"}],
        "hints": {"SoftwareRequirement": {"packages": [{"package": "metagenomic-agent", "version": [__version__]}]}},
    }
    cwl_path = outdir / "meta_agent.cwl"
    cwl_path.write_text(json.dumps(cwl, indent=2), encoding="utf-8")

    nf_params = outdir / "nextflow_params.json"
    nf_params.write_text(
        json.dumps(
            {
                "input": state.get("input_path"),
                "outdir": state.get("outdir"),
                "mode": state.get("mode"),
                "query": state.get("user_query"),
                "seed": seed,
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
        f"- Seed: `{seed}`\n"
        "- `run_manifest.json`: DAG, config subset, contracts, routing, seed\n"
        "- `seeds.json`: run-level and per-node seed pointers\n"
        "- `meta_agent.cwl`: CWL CommandLineTool wrapper\n"
        "- `nextflow_params.json`: parameters for Nextflow handoff\n"
        "- `../workflow/reproducible.nf` / `reproducible.smk`: post-run peer-review workflows\n"
        "- `../workflow/config_snapshot.yaml`: full config snapshot\n"
        "- `../context/pipeline_summary.json`: statistical metadata (no raw sequences)\n"
        "- Also see `../report/reproduce.sh` and `../logs/events.jsonl`\n",
        encoding="utf-8",
    )
    return {
        "manifest": str(manifest_path),
        "cwl": str(cwl_path),
        "nextflow_params": str(nf_params),
        "seeds": str(seeds_copy),
        "readme": str(readme),
        "reproducible_nf": wf["nextflow"],
        "reproducible_smk": wf["snakemake"],
        "config_snapshot": wf["config_snapshot"],
        "run_seed": str(seed),
    }
