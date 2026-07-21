"""CLI entrypoint: meta-agent."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich import print as rprint
from rich.panel import Panel

from metagenomic_agent.config_loader import load_config
from metagenomic_agent.graph import run_pipeline
from metagenomic_agent.state import AgentState

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Metagenomic Research Agent")


@app.command("run")
def run(
    input: Path = typer.Option(..., "--input", "-i", help="FASTQ file or directory"),
    outdir: Path = typer.Option(Path("./results"), "--outdir", "-o", help="Output directory"),
    mode: str = typer.Option("mock", "--mode", "-m", help="mock | local | conda | docker"),
    query: str = typer.Option(
        "Analyze shotgun metagenomic samples and identify microbial biomarkers.",
        "--query",
        "-q",
    ),
    metadata: Optional[Path] = typer.Option(
        None, "--metadata", help="TSV/CSV with sample_id,group columns"
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="YAML config override"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm HITL checkpoints"),
) -> None:
    """Run the autonomous metagenomic research agent."""
    load_dotenv()
    if mode not in {"mock", "local", "conda", "docker"}:
        raise typer.BadParameter("mode must be mock, local, conda, or docker")

    outdir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(config, overrides={"mode": mode})
    cfg["mode"] = mode
    # --yes forces auto-confirm; otherwise honor config.hitl.auto_confirm (default false for safety)
    auto = bool(yes) if yes else bool(cfg.get("hitl", {}).get("auto_confirm", False))
    cfg.setdefault("hitl", {})["auto_confirm"] = auto

    import uuid

    initial: AgentState = {
        "user_query": query,
        "input_path": str(input.expanduser().resolve()),
        "outdir": str(outdir.expanduser().resolve()),
        "mode": mode,  # type: ignore[typeddict-item]
        "config": cfg,
        "samples": [],
        "metadata_path": str(metadata.expanduser().resolve()) if metadata else None,
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
        "hitl_auto_confirm": auto,
        "hitl_resolved": False,
        "report_path": None,
        "error": None,
        "run_id": str(uuid.uuid4())[:8],
    }

    rprint(Panel.fit(f"[bold]Metagenomic Research Agent[/bold]\nmode={mode}\nquery={query}"))
    final = run_pipeline(initial)
    for msg in final.get("messages", [])[-16:]:
        rprint(f"• {msg}")
    report = final.get("report_path")
    if report:
        rprint(f"\n[green]Final report:[/green] {report}")
    critic = final.get("critic") or {}
    rprint(f"[cyan]Critic:[/cyan] {'PASS' if critic.get('passed', True) else 'WARNINGS'}")


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Start the HTTP API server."""
    import uvicorn

    from metagenomic_agent.api.server import app as fastapi_app

    uvicorn.run(fastapi_app, host=host, port=port)


@app.command("version")
def version() -> None:
    from metagenomic_agent import __version__

    rprint(__version__)


if __name__ == "__main__":
    app()
