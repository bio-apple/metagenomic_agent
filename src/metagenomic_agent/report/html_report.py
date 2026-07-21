"""HTML report + reproducible script packing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Template

from metagenomic_agent.report.interpreter import interpret

HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>Metagenomic Agent Report</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    body { font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif; margin: 2rem; background: #f7faf8; color: #1a2e28; }
    h1 { font-size: 1.8rem; }
    .card { background: white; padding: 1.2rem 1.5rem; margin: 1rem 0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    code { background: #eef3f0; padding: 0.1rem 0.3rem; border-radius: 4px; }
    pre { background: #1a2e28; color: #e8f5ef; padding: 1rem; overflow: auto; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>宏基因组分析报告</h1>
  <div class="card">
    <p><b>查询：</b>{{ query }}</p>
    <p><b>模式：</b>{{ mode }} | <b>验证：</b>{{ validation_status }}</p>
  </div>
  <div class="card">
    <h2>物种相对丰度</h2>
    <div id="taxplot" style="height:420px;"></div>
  </div>
  <div class="card">
    <h2>解读</h2>
    <div>{{ interpretation_html | safe }}</div>
  </div>
  <div class="card">
    <h2>产物路径</h2>
    <pre>{{ artifacts_json }}</pre>
  </div>
  <script>
    var data = {{ plot_data | safe }};
    Plotly.newPlot('taxplot', data.traces, data.layout, {responsive: true});
  </script>
</body>
</html>
"""
)


def _load_abundance(path: str | None) -> list[tuple[str, float]]:
    if not path or not Path(path).exists():
        return []
    rows: list[tuple[str, float]] = []
    for line in Path(path).read_text().splitlines()[1:]:
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            try:
                rows.append((parts[0], float(parts[1])))
            except ValueError:
                continue
    return rows


def _plot_payload(state: dict[str, Any]) -> dict[str, Any]:
    tax = state.get("artifacts", {}).get("taxonomy", {})
    traces = []
    for sid, art in tax.items():
        path = art.get("kraken2_abundance") or art.get("metaphlan_abundance")
        rows = _load_abundance(path)[:10]
        if not rows:
            continue
        traces.append(
            {
                "type": "bar",
                "name": sid,
                "x": [r[0] for r in rows],
                "y": [r[1] for r in rows],
            }
        )
    return {
        "traces": traces or [{"type": "bar", "x": ["N/A"], "y": [0], "name": "empty"}],
        "layout": {
            "title": "Top genera (relative abundance)",
            "barmode": "group",
            "yaxis": {"title": "relative abundance"},
        },
    }


def _md_to_html(md: str) -> str:
    # Minimal markdown-ish rendering for headings/bullets
    html_lines: list[str] = []
    for line in md.splitlines():
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)


def write_report(state: dict[str, Any]) -> dict[str, str]:
    outdir = Path(state["outdir"]) / "report"
    outdir.mkdir(parents=True, exist_ok=True)
    interpretation = interpret(state)
    validation = state.get("validation") or {}
    html = HTML_TEMPLATE.render(
        query=state.get("user_query", ""),
        mode=state.get("mode", ""),
        validation_status="PASS" if validation.get("passed") else "FAIL/UNKNOWN",
        interpretation_html=_md_to_html(interpretation),
        artifacts_json=json.dumps(state.get("artifacts", {}), indent=2, ensure_ascii=False)[:8000],
        plot_data=json.dumps(_plot_payload(state)),
    )
    html_path = outdir / "report.html"
    html_path.write_text(html, encoding="utf-8")

    methods = outdir / "methods.md"
    methods.write_text(
        "# Methods\n\n"
        "Pipeline orchestrated by metagenomic-agent (LangGraph MVP).\n\n"
        "- QC: fastp\n"
        "- Host removal: Bowtie2 (HG38) when enabled\n"
        "- Taxonomy: Kraken2+Bracken / MetaPhlAn\n"
        "- Function: DIAMOND (HUMAnN optional)\n",
        encoding="utf-8",
    )

    (outdir / "interpretation.md").write_text(interpretation, encoding="utf-8")

    reproduce = outdir / "reproduce.sh"
    reproduce.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"# Regenerated from metagenomic-agent run\n"
        f"meta-agent run --input {state.get('input_path')} --outdir {state.get('outdir')} "
        f"--mode {state.get('mode')} --yes\n",
        encoding="utf-8",
    )
    reproduce.chmod(0o755)

    manifest = outdir / "paths.json"
    manifest.write_text(
        json.dumps(
            {
                "html": str(html_path),
                "methods": str(methods),
                "interpretation": str(outdir / "interpretation.md"),
                "reproduce": str(reproduce),
                "artifacts": state.get("artifacts", {}),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {
        "html": str(html_path),
        "methods": str(methods),
        "reproduce": str(reproduce),
        "manifest": str(manifest),
    }
