from pathlib import Path

from metagenomic_agent.config_loader import load_config
from metagenomic_agent.graph import run_pipeline
from metagenomic_agent.state import AgentState

from conftest import write_tiny_fastq


def test_graph_dryrun_mock(tmp_path: Path):
    fq = tmp_path / "fastq"
    write_tiny_fastq(fq / "gut_R1.fastq")
    write_tiny_fastq(fq / "gut_R2.fastq")
    out = tmp_path / "out"
    cfg = load_config(overrides={"mode": "mock", "pipeline": {"enable_assembly": False}})

    initial: AgentState = {
        "user_query": "分析我的肠道宏基因组 FASTQ 数据",
        "input_path": str(fq),
        "outdir": str(out),
        "mode": "mock",
        "config": cfg,
        "samples": [],
        "dag": [],
        "artifacts": {},
        "messages": [],
        "validation": None,
        "retry_count": 0,
        "max_retries": 2,
        "hitl_pending": [],
        "hitl_auto_confirm": True,
        "report_path": None,
        "error": None,
    }
    final = run_pipeline(initial)
    assert final.get("report_path")
    assert Path(final["report_path"]).exists()
    assert final.get("validation", {}).get("passed") is True
    assert "qc_host" in final.get("artifacts", {})
    assert "taxonomy" in final.get("artifacts", {})
