"""Workflow engine params — Agent emits YAML/JSON; Nextflow/Snakemake execute.

Policy: never let the LLM invent ad-hoc shell pipelines for production compute.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from metagenomic_agent.tools.schemas import TOOL_SCHEMA_REGISTRY, validate_many


def _plan_time_params(tool: str, raw: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Fill placeholders so schema validation works at plan time without free-form shell."""
    sample0 = (state.get("samples") or [{}])[0] if state.get("samples") else {}
    outdir = state.get("outdir") or "results"
    data = dict(raw)
    data.setdefault("outdir", outdir)
    data.setdefault("threads", data.get("threads") or 8)
    data.setdefault("memory_gb", data.get("memory_gb") or 16)
    r1 = sample0.get("r1") or data.get("r1") or data.get("clean_r1") or f"{outdir}/reads_R1.fastq"
    r2 = sample0.get("r2") or data.get("r2") or data.get("clean_r2")
    name = (tool or "").lower()
    if name in {"fastp", "trimmomatic", "kraken2", "megahit", "metaphlan", "metaphlan4"}:
        data.setdefault("r1", r1)
        if r2:
            data.setdefault("r2", r2)
    if name == "fastqc":
        data.setdefault("inputs", [r1] + ([r2] if r2 else []))
    if name == "kraken2":
        data.setdefault("db", data.get("db") or "<kraken2_db>")
    if name == "metabat2":
        data.setdefault("contigs", data.get("contigs") or f"{outdir}/contigs.fa")
    if name in {"humann3", "humann"}:
        data.setdefault("input", data.get("input") or r1)
    if name == "checkm2":
        data.setdefault("bins_dir", data.get("bins") or data.get("bins_dir") or f"{outdir}/bins")
    return data


def build_workflow_params(state: dict[str, Any]) -> dict[str, Any]:
    """Structured task + resource params for external workflow engines."""
    cfg = state.get("config") or {}
    linux = cfg.get("linux") or {}
    docker = cfg.get("docker") or {}
    paths = cfg.get("paths") or {}
    bio = (state.get("artifacts") or {}).get("bio_reasoning") or {}
    specialist = (state.get("artifacts") or {}).get("tool_specialist") or {}
    specs = specialist.get("specialists") or []

    threads = int(linux.get("threads") or docker.get("threads") or 8)
    memory_gb = int(linux.get("memory_gb") or 32)

    tasks = []
    for n in state.get("dag") or []:
        if n.get("status") == "skipped":
            continue
        tasks.append(
            {
                "id": n.get("id"),
                "agent": n.get("agent"),
                "tools": n.get("tools") or [],
                "params": n.get("params") or {},
                "depends_on": n.get("depends_on") or [],
            }
        )

    tool_calls = []
    for s in specs:
        tool = s.get("tool")
        merged = {
            **(s.get("params") or {}),
            "threads": threads,
            "memory_gb": memory_gb,
            "outdir": state.get("outdir"),
        }
        tool_calls.append({"tool": tool, "params": _plan_time_params(str(tool or ""), merged, state)})

    # Also emit schemas for core tools present on the DAG even if specialist missed them
    for n in state.get("dag") or []:
        for t in n.get("tools") or []:
            if t in TOOL_SCHEMA_REGISTRY and not any(tc.get("tool") == t for tc in tool_calls):
                tool_calls.append(
                    {
                        "tool": t,
                        "params": _plan_time_params(
                            t,
                            {**(n.get("params") or {}), "threads": threads, "memory_gb": memory_gb},
                            state,
                        ),
                    }
                )

    validations = validate_many(tool_calls, strict=False)
    invalid = [v.model_dump() for v in validations if not v.ok]

    params = {
        "schema_version": "1.0",
        "policy": "agent_emits_params_engine_executes_no_freeform_shell",
        "input": state.get("input_path"),
        "outdir": state.get("outdir"),
        "mode": state.get("mode"),
        "query": state.get("user_query"),
        "run_id": state.get("run_id"),
        "threads": threads,
        "memory_gb": memory_gb,
        "paths": {
            "kraken2_db": paths.get("kraken2_db") or "",
            "metaphlan_db": paths.get("metaphlan_db") or "",
            "host_index": paths.get("host_index") or "",
            "gtdb": paths.get("gtdb") or "",
            "diamond_db": paths.get("diamond_db") or "",
        },
        "bio_reasoning": {
            "study_goal": bio.get("study_goal"),
            "assay": bio.get("recommended_assay"),
            "enable_host_filter": bio.get("enable_host_filter"),
            "enable_function": bio.get("enable_function"),
            "enable_statistics": bio.get("enable_statistics"),
            "enable_assembly": bio.get("enable_assembly"),
            "assembler": bio.get("assembler_preference"),
        },
        "tasks": tasks,
        "tool_calls": [
            {
                "tool": v.tool,
                "ok": v.ok,
                "params": v.params if v.ok else (tool_calls[i].get("params") if i < len(tool_calls) else {}),
                "errors": v.errors,
            }
            for i, v in enumerate(validations)
        ],
        "validation_errors": invalid,
        "resume": {
            "nextflow": "-resume",
            "snakemake": "--rerun-incomplete",
            "langgraph_cache": bool((cfg.get("cache") or {}).get("enabled", True)),
        },
        "executor": (linux.get("nextflow_executor") or "local"),
        "slurm": bool(linux.get("slurm")),
        "slurm_queue": linux.get("slurm_queue") or "normal",
    }
    return params


def write_workflow_params(state: dict[str, Any]) -> dict[str, str]:
    """Write workflow/params.yaml + params.json for Nextflow/Snakemake handoff."""
    params = build_workflow_params(state)
    out = Path(state["outdir"]) / "workflow"
    out.mkdir(parents=True, exist_ok=True)
    yml = out / "params.yaml"
    js = out / "params.json"
    yml.write_text(yaml.safe_dump(params, sort_keys=False, allow_unicode=True), encoding="utf-8")
    js.write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")

    # Engine-specific thin wrappers that ONLY read params (no LLM shell)
    nf_params = out / "nextflow_params.json"
    nf_params.write_text(
        json.dumps(
            {
                "input": params["input"],
                "outdir": params["outdir"],
                "mode": params["mode"],
                "query": params["query"],
                "threads": params["threads"],
                "memory_gb": params["memory_gb"],
                "params_file": str(yml),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    smk_cfg = out / "snakemake_config.yaml"
    smk_cfg.write_text(
        yaml.safe_dump(
            {
                "input_dir": params["input"],
                "outdir": params["outdir"],
                "mode": params["mode"],
                "query": params["query"],
                "threads": params["threads"],
                "memory_gb": params["memory_gb"],
                "agent_params": str(yml),
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    readme = out / "ENGINE_README.md"
    readme.write_text(
        "# Workflow engine handoff\n\n"
        "The Agent writes **validated** `params.yaml` / `params.json`.\n"
        "Nextflow/Snakemake own execution, env, and `-resume` / `--rerun-incomplete`.\n"
        "Do **not** paste LLM-generated shell pipelines into production.\n\n"
        "```bash\n"
        f"nextflow run workflow/nextflow/main.nf -params-file {yml} -resume\n"
        f"snakemake -s workflow/Snakefile --configfile {smk_cfg} --rerun-incomplete -j {params['threads']}\n"
        "```\n",
        encoding="utf-8",
    )
    return {
        "params_yaml": str(yml),
        "params_json": str(js),
        "nextflow_params": str(nf_params),
        "snakemake_config": str(smk_cfg),
        "readme": str(readme),
        "n_validation_errors": str(len(params["validation_errors"])),
    }
