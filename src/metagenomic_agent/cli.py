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

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Metagenomic bioinformatics agent")


@app.command("run")
def run(
    input: Path = typer.Option(..., "--input", "-i", help="FASTQ file or directory"),
    outdir: Path = typer.Option(Path("./results"), "--outdir", "-o", help="Output directory"),
    mode: str = typer.Option("mock", "--mode", "-m", help="mock | docker"),
    query: str = typer.Option("分析我的肠道宏基因组 FASTQ 数据", "--query", "-q"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="YAML config override"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm HITL checkpoints"),
) -> None:
    """Run the metagenomic agent pipeline."""
    load_dotenv()
    if mode not in {"mock", "docker"}:
        raise typer.BadParameter("mode must be mock or docker")

    outdir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(config, overrides={"mode": mode, "hitl": {"auto_confirm": yes or True}})
    cfg["mode"] = mode

    initial: AgentState = {
        "user_query": query,
        "input_path": str(input.expanduser().resolve()),
        "outdir": str(outdir.expanduser().resolve()),
        "mode": mode,  # type: ignore[typeddict-item]
        "config": cfg,
        "samples": [],
        "dag": [],
        "artifacts": {},
        "messages": [],
        "validation": None,
        "retry_count": 0,
        "max_retries": int(cfg.get("max_retries", 2)),
        "hitl_pending": [],
        "hitl_auto_confirm": bool(yes or cfg.get("hitl", {}).get("auto_confirm", True)),
        "report_path": None,
        "error": None,
    }

    rprint(Panel.fit(f"[bold]meta-agent[/bold] mode={mode}\ninput={initial['input_path']}"))
    final = run_pipeline(initial)
    for msg in final.get("messages", [])[-12:]:
        rprint(f"• {msg}")
    report = final.get("report_path")
    if report:
        rprint(f"\n[green]Report:[/green] {report}")
    validation = final.get("validation") or {}
    status = "PASS" if validation.get("passed") else "FAIL"
    rprint(f"[cyan]Validation:[/cyan] {status}")


@app.command("version")
def version() -> None:
    from metagenomic_agent import __version__

    rprint(__version__)


if __name__ == "__main__":
    app()
