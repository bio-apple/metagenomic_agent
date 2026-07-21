"""Celery async task queue for Linux Agent Hub."""

from __future__ import annotations

from typing import Any

try:
    from celery import Celery
except ImportError:  # optional dependency
    Celery = None  # type: ignore


def make_celery(broker_url: str = "redis://localhost:6379/0", backend_url: str | None = None):
    if Celery is None:
        raise ImportError("Install celery and redis to use async execution: pip install celery redis")
    app = Celery("metagenomic_agent", broker=broker_url, backend=backend_url or broker_url)
    app.conf.update(task_track_started=True, worker_prefetch_multiplier=1)

    @app.task(name="metagenomic_agent.run_analysis", bind=True)
    def run_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        from metagenomic_agent.config_loader import load_config
        from metagenomic_agent.graph import run_pipeline
        from metagenomic_agent.state import AgentState

        cfg = load_config(payload.get("config_path"), overrides={"mode": payload.get("mode", "mock")})
        initial: AgentState = {
            "user_query": payload.get("query", "Analyze metagenomic samples"),
            "input_path": payload["input_path"],
            "outdir": payload.get("outdir", "./results"),
            "mode": payload.get("mode", "mock"),  # type: ignore[typeddict-item]
            "config": cfg,
            "samples": [],
            "metadata_path": payload.get("metadata_path"),
            "tasks": [],
            "dag": [],
            "artifacts": {},
            "messages": [],
            "validation": None,
            "critic": None,
            "literature": None,
            "statistics": None,
            "retry_count": 0,
            "max_retries": int(cfg.get("max_retries", 2)),
            "hitl_pending": [],
            "hitl_auto_confirm": True,
            "report_path": None,
            "error": None,
        }
        self.update_state(state="PROGRESS", meta={"stage": "running"})
        final = run_pipeline(initial)
        return {
            "report_path": final.get("report_path"),
            "messages": final.get("messages", [])[-20:],
            "critic_passed": bool((final.get("critic") or {}).get("passed", True)),
        }

    return app, run_analysis


# Default app when celery is installed
if Celery is not None:
    celery_app, run_analysis_task = make_celery()
else:
    celery_app = None
    run_analysis_task = None
