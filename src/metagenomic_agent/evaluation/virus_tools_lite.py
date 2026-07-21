"""Lite virus-identification tool regression (informed by Wu et al. 2024 benchmarking).

Not a reproduction of the multi-biome study — CI harness for multi-caller suite behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools.context import ToolContext
from metagenomic_agent.tools.virus import run_virus_suite


def run_virus_tool_scenarios(outdir: str | Path) -> dict[str, Any]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ctx = ToolContext(mode="mock", outdir=outdir)
    contigs = outdir / "toy.contigs.fa"
    contigs.write_text(">c1\n" + ("ATGC" * 500) + "\n", encoding="utf-8")
    result = run_virus_suite(str(contigs), outdir / "virus", ctx, "toy")
    ok = bool(result.get("genomad")) and bool(result.get("consensus"))
    callers = (result.get("consensus") or {}).get("callers") or []
    report = {
        "ok": ok,
        "callers": callers,
        "n_virsorter2": (result.get("consensus") or {}).get("n_virsorter2"),
        "n_genomad": (result.get("consensus") or {}).get("n_genomad"),
        "checkv_skipped": bool((result.get("checkv") or {}).get("skipped")),
        "note": "Toy multi-caller regression; see Wu et al. 2024 for real-world biome benchmarks.",
    }
    (outdir / "virus_tool_scenarios.json").write_text(
        __import__("json").dumps(report, indent=2), encoding="utf-8"
    )
    return report
