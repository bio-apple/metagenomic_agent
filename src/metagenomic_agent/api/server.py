"""HTTP API for Metagenomic Research Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from metagenomic_agent import __version__
from metagenomic_agent.config_loader import load_config
from metagenomic_agent.graph import run_pipeline
from metagenomic_agent.state import AgentState

app = FastAPI(
    title="Metagenomic Research Agent API",
    description="Autonomous AI agent system for end-to-end metagenomic analysis",
    version=__version__,
)


class AnalyzeRequest(BaseModel):
    input_path: str = Field(..., description="FASTQ file or directory")
    outdir: str = Field("./results", description="Output directory")
    query: str = Field(
        "Analyze shotgun metagenomic samples from IBD patients and healthy controls. "
        "Identify microbial biomarkers."
    )
    mode: Literal["mock", "local", "conda", "docker"] = "mock"
    metadata_path: Optional[str] = None
    config_path: Optional[str] = None


class AnalyzeResponse(BaseModel):
    report_path: Optional[str]
    critic_passed: bool
    messages: list[str]
    artifacts_keys: list[str]
    paths: dict[str, Any]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    input_path = Path(req.input_path).expanduser()
    if not input_path.exists():
        raise HTTPException(status_code=400, detail=f"input_path not found: {req.input_path}")

    outdir = Path(req.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(req.config_path, overrides={"mode": req.mode})
    cfg.setdefault("hitl", {})["auto_confirm"] = True

    import uuid

    initial: AgentState = {
        "user_query": req.query,
        "input_path": str(input_path.resolve()),
        "outdir": str(outdir.resolve()),
        "mode": req.mode,
        "config": cfg,
        "samples": [],
        "metadata_path": str(Path(req.metadata_path).resolve()) if req.metadata_path else None,
        "tasks": [],
        "dag": [],
        "artifacts": {},
        "messages": [],
        "agent_messages": [],
        "validation": None,
        "critic": None,
        "literature": None,
        "statistics": None,
        "retry_count": 0,
        "max_retries": int(cfg.get("max_retries", 2)),
        "hitl_pending": [],
        "hitl_auto_confirm": True,
        "hitl_resolved": False,
        "report_path": None,
        "error": None,
        "run_id": str(uuid.uuid4())[:8],
    }
    try:
        final = run_pipeline(initial)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    paths_file = outdir / "paths.json"
    paths: dict[str, Any] = {}
    if paths_file.exists():
        import json

        paths = json.loads(paths_file.read_text())

    critic = final.get("critic") or {}
    return AnalyzeResponse(
        report_path=final.get("report_path"),
        critic_passed=bool(critic.get("passed", True)),
        messages=list(final.get("messages", []))[-30:],
        artifacts_keys=sorted(final.get("artifacts", {}).keys()),
        paths=paths,
    )
