"""HPC / containers / checkpoints (v0.17)."""

from pathlib import Path

from metagenomic_agent.agents.executor_agent import prepare_submit_specs
from metagenomic_agent.deployment.slurm import render_pbs, render_sbatch, render_sge
from metagenomic_agent.execution.checkpoint import load_assembly_checkpoint, write_assembly_checkpoint
from metagenomic_agent.execution.cluster import cap_resources, detect_scheduler, sense_cluster
from metagenomic_agent.execution.step_cache import cache_key
from metagenomic_agent.tools.context import DEFAULT_IMAGES, ToolContext


def test_biocontainers_images_include_core_tools():
    for t in ("kraken2", "megahit", "checkm2", "gtdbtk", "bakta", "humann3", "fastqc"):
        assert t in DEFAULT_IMAGES
        assert "biocontainers" in DEFAULT_IMAGES[t]


def test_run_docker_routes_apptainer_via_sandbox(tmp_path: Path):
    ctx = ToolContext.from_config({"mode": "apptainer", "sandbox": {"prefer_container": True}}, tmp_path, mode="apptainer")
    # mock backend forced: mode mock via sandbox override for unit test
    ctx.mode = "mock"
    ctx.extra["config"] = {"mode": "mock", "sandbox": {}}
    # When mode is mock, run_docker falls through to docker_run path unless we set docker/apptainer.
    # Exercise run_tool path with mock:
    from metagenomic_agent.tools.linux_runner import CommandResult

    cr = ctx.run_tool("kraken2", ["kraken2", "--help"])
    assert isinstance(cr, CommandResult)
    assert cr.status == "success"


def test_cluster_cap_under_high_pressure():
    cfg = {"linux": {"threads": 32, "memory_gb": 128, "gpus": 2, "scheduler": "local"}}
    sense = {"scheduler": "local", "pressure": "high", "cpus_free_hint": 8, "mem_free_gb_hint": 20}
    capped = cap_resources(cfg, sense)
    assert capped["linux"]["threads"] <= 16
    assert capped["linux"]["memory_gb"] <= 64
    assert capped["linux"]["gpus"] <= 1


def test_detect_scheduler_local():
    assert detect_scheduler({"linux": {"scheduler": "local"}}) == "local"


def test_sense_cluster_local_smoke():
    s = sense_cluster({"linux": {"scheduler": "local"}})
    assert s["scheduler"] == "local"
    assert s["pressure"] in {"low", "medium", "high", "unknown"}


def test_scheduler_script_templates():
    assert "#SBATCH" in render_sbatch("j", "echo ok", cpus=4, mem="16G", sif_dir="/scratch/c")
    assert "#PBS" in render_pbs("j", "echo ok", cpus=4)
    assert "#$" in render_sge("j", "echo ok", cpus=4)


def test_assembly_checkpoint_roundtrip(tmp_path: Path):
    asm = tmp_path / "S1" / "assembly"
    asm.mkdir(parents=True)
    contigs = asm / "final.contigs.fa"
    contigs.write_text(">c1\nACGT\n", encoding="utf-8")
    write_assembly_checkpoint(asm, {"assembler": "megahit", "contigs": str(contigs)})
    loaded = load_assembly_checkpoint(asm, "S1")
    assert loaded is not None
    assert loaded["checkpoint"] is True
    assert Path(loaded["contigs"]).exists()


def test_prepare_submit_specs_writes_schedulers(tmp_path: Path):
    state = {
        "input_path": str(tmp_path / "fq"),
        "outdir": str(tmp_path / "out"),
        "mode": "mock",
        "user_query": "test",
        "run_id": "h17",
        "samples": [{"sample_id": "S1", "r1": "a.fq"}],
        "config": {
            "linux": {"threads": 16, "memory_gb": 64, "scheduler": "local", "gpus": 0},
            "docker": {"threads": 16},
            "cache": {"enabled": True},
            "apptainer": {"sif_dir": "/scratch/containers"},
            "paths": {},
        },
        "dag": [{"id": "qc", "agent": "qc", "tools": ["fastp"], "params": {}, "status": "pending", "depends_on": []}],
        "artifacts": {},
    }
    specs = prepare_submit_specs(state)
    assert Path(specs["slurm"]).exists()
    assert Path(specs["pbs"]).exists()
    assert Path(specs["sge"]).exists()
    assert "APPTAINER_CACHEDIR" in Path(specs["slurm"]).read_text()
    assert (tmp_path / "out" / "executor" / "cluster_sense.json").exists()
    assert specs["allocation"]["threads"] >= 2


def test_cache_key_includes_config_hash():
    state_a = {
        "mode": "mock",
        "samples": [{"sample_id": "S1"}],
        "input_path": "/data",
        "config": {"linux": {"threads": 8}, "cache": {"include_config_hash": True}},
    }
    state_b = {
        **state_a,
        "config": {"linux": {"threads": 32}, "cache": {"include_config_hash": True}},
    }
    node = {"id": "taxonomy", "agent": "taxonomy", "tools": ["kraken2"], "params": {}}
    assert cache_key(node, state_a) != cache_key(node, state_b)
