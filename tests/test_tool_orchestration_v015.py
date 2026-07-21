"""Tool schema validation + workflow params + self-heal loop (v0.15)."""

from pathlib import Path

from metagenomic_agent.execution.self_heal import (
    apply_self_heal,
    classify_from_errors,
    patch_workflow_params_on_heal,
    summarize_error_logs,
)
from metagenomic_agent.execution.workflow_params import build_workflow_params, write_workflow_params
from metagenomic_agent.tools.linux_runner import classify_error
from metagenomic_agent.tools.schemas import validate_tool_params
from metagenomic_agent.tools.sandbox import ToolCallRequest, sandbox_from_config


def test_kraken2_schema_ok():
    r = validate_tool_params(
        "kraken2",
        {"r1": "a.fq", "db": "database/kraken_db", "threads": 8, "memory_gb": 32, "outdir": "results"},
    )
    assert r.ok
    assert r.params["threads"] == 8


def test_kraken2_schema_rejects_shell_injection():
    r = validate_tool_params(
        "kraken2",
        {"r1": "a.fq; rm -rf /", "db": "db", "threads": 8, "memory_gb": 16, "outdir": "results"},
    )
    assert not r.ok


def test_megahit_threads_bounds():
    r = validate_tool_params(
        "megahit",
        {"r1": "a.fq", "threads": 0, "memory_gb": 32, "outdir": "results"},
    )
    assert not r.ok


def test_classify_missing_db_and_file():
    assert classify_error(1, "Cannot find Kraken 2 database directory") == "missing_db"
    assert classify_error(1, "No such file or directory: results/clean_R1.fastq") == "missing_file"


def test_self_heal_missing_db():
    actions = classify_from_errors([{"classified": "missing_db", "stderr": "hash.k2d not found"}])
    assert "fix_db_path" in actions or "switch_taxonomy_tool" in actions


def test_error_log_digest():
    digest = summarize_error_logs(
        [{"node": "taxonomy", "classified": "oom", "stderr": "line1\nOut of memory\nKilled"}]
    )
    assert "taxonomy" in digest
    assert "oom" in digest


def test_write_workflow_params(tmp_path: Path):
    state = {
        "input_path": str(tmp_path / "fq"),
        "outdir": str(tmp_path / "out"),
        "mode": "mock",
        "user_query": "test",
        "run_id": "t1",
        "samples": [{"r1": "a_R1.fq", "r2": "a_R2.fq"}],
        "config": {"linux": {"threads": 4, "memory_gb": 16}, "paths": {"kraken2_db": "database/kraken_db"}},
        "dag": [
            {
                "id": "taxonomy",
                "agent": "taxonomy",
                "tools": ["kraken2", "megahit"],
                "params": {},
                "status": "pending",
                "depends_on": [],
            }
        ],
        "artifacts": {
            "tool_specialist": {
                "specialists": [
                    {"tool": "kraken2", "params": {"db": "database/kraken_db", "r1": "a_R1.fq"}},
                    {"tool": "megahit", "params": {"r1": "a_R1.fq"}},
                ]
            }
        },
    }
    paths = write_workflow_params(state)
    assert Path(paths["params_yaml"]).exists()
    assert Path(paths["params_json"]).exists()
    params = build_workflow_params(state)
    assert params["policy"].startswith("agent_emits_params")
    assert params["resume"]["nextflow"] == "-resume"
    tools = {tc["tool"] for tc in params["tool_calls"]}
    assert "kraken2" in tools
    assert "megahit" in tools


def test_patch_params_on_heal():
    params = {"threads": 16, "memory_gb": 32, "tool_calls": [{"tool": "metaspades", "params": {}}]}
    patched = patch_workflow_params_on_heal(
        params, {"linux": {"memory_gb": 64, "threads": 8}, "docker": {"threads": 8}}, ["increase_memory", "downgrade_assembler"]
    )
    assert patched["memory_gb"] == 64
    assert patched["threads"] == 8
    assert patched["tool_calls"][0]["tool"] == "megahit"
    assert patched["heal_generation"] == 1


def test_sandbox_rejects_bad_schema_when_provided():
    ex = sandbox_from_config({"mode": "mock"})
    resp = ex.execute(
        ToolCallRequest(tool="kraken2", argv=["kraken2"], threads=8, memory_gb=16),
        schema_params={"r1": "x;y", "db": "db", "threads": 8, "memory_gb": 16, "outdir": "results"},
    )
    assert not resp.ok
    assert "Schema" in resp.user_message or "schema" in resp.user_message.lower() or "validation" in resp.user_message.lower()
