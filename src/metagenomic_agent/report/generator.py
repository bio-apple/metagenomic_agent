"""Report Generator — final scientific HTML report and path packing."""

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
  <title>Metagenomic Research Agent — Final Report</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    body { font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif; margin: 2rem; background: #f4f7f5; color: #14241e; }
    h1 { font-size: 1.9rem; margin-bottom: .3rem; }
    .sub { color: #4a6358; margin-bottom: 1.5rem; }
    .card { background: #fff; padding: 1.2rem 1.5rem; margin: 1rem 0; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.07); }
    pre { background: #173028; color: #e7f6ee; padding: 1rem; overflow: auto; border-radius: 8px; font-size: .85rem; }
    .warn { color: #9a3412; }
    .ok { color: #166534; }
    ul { line-height: 1.6; }
  </style>
</head>
<body>
  <h1>Metagenomic Research Agent</h1>
  <p class="sub">{{ query }}</p>

  <div class="card">
    <h2>Run Status</h2>
    <p>Mode: <b>{{ mode }}</b> |
       Critic: <span class="{{ 'ok' if critic_passed else 'warn' }}">{{ critic_status }}</span> |
       Plan source: {{ plan_source }}</p>
    <p>Outputs follow documentation layout under <code>results/</code>.</p>
  </div>

  <div class="card">
    <h2>Supervisor Plan</h2>
    <pre>{{ plan_json }}</pre>
  </div>

  <div class="card">
    <h2>Taxonomy Profile</h2>
    <div id="taxplot" style="height:420px;"></div>
  </div>

  <div class="card">
    <h2>Biomarkers</h2>
    <pre>{{ biomarkers }}</pre>
  </div>

  <div class="card">
    <h2>Critic</h2>
    <ul>
    {% for w in warnings %}<li class="warn">{{ w }}</li>{% else %}<li class="ok">No warnings</li>{% endfor %}
    </ul>
    <h3>Recommendations</h3>
    <ul>{% for r in recommendations %}<li>{{ r }}</li>{% endfor %}</ul>
  </div>

  <div class="card">
    <h2>Literature</h2>
    <div>{{ literature_html | safe }}</div>
  </div>

  <div class="card">
    <h2>Biological Interpretation</h2>
    <div>{{ interpretation_html | safe }}</div>
  </div>

  <div class="card">
    <h2>Key Paths</h2>
    <pre>{{ paths_json }}</pre>
  </div>

  <script>
    var data = {{ plot_data | safe }};
    Plotly.newPlot('taxplot', data.traces, data.layout, {responsive: true});
  </script>
</body>
</html>
"""
)


def _md_to_html(md: str) -> str:
    html_lines: list[str] = []
    for line in md.splitlines():
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h2>{line[2:]}</h2>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)


def _load_abundance(path: str | None) -> list[tuple[str, float]]:
    if not path or not Path(path).exists():
        return []
    rows: list[tuple[str, float]] = []
    for line in Path(path).read_text().splitlines()[1:]:
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            try:
                # taxonomy_profile.tsv has sample genus abundance tool
                if len(parts) >= 3 and parts[0] and not parts[0].replace(".", "", 1).isdigit():
                    # detect header-like sample column
                    try:
                        float(parts[1])
                        rows.append((parts[0], float(parts[1])))
                    except ValueError:
                        rows.append((parts[1], float(parts[2])))
                else:
                    rows.append((parts[0], float(parts[1])))
            except ValueError:
                continue
    return rows[:12]


def _plot_payload(state: dict[str, Any]) -> dict[str, Any]:
    tax = state.get("artifacts", {}).get("taxonomy", {})
    traces = []
    for sid, art in tax.items():
        path = art.get("kraken2_abundance") or art.get("metaphlan_abundance")
        rows = _load_abundance(path)
        if not rows:
            continue
        traces.append({"type": "bar", "name": sid, "x": [r[0] for r in rows], "y": [r[1] for r in rows]})
    return {
        "traces": traces or [{"type": "bar", "x": ["N/A"], "y": [0], "name": "empty"}],
        "layout": {"title": "Top genera", "barmode": "group", "yaxis": {"title": "relative abundance"}},
    }


def generate(state: dict[str, Any]) -> dict[str, str]:
    outdir = Path(state["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)

    interpretation = interpret(state)
    critic = state.get("critic") or {}
    literature = state.get("literature") or state.get("artifacts", {}).get("literature") or {}
    lit_md = ""
    lit_path = literature.get("path") if isinstance(literature, dict) else None
    if lit_path and Path(lit_path).exists():
        lit_md = Path(lit_path).read_text(encoding="utf-8")

    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    biomarkers = ""
    if stats.get("biomarkers") and Path(stats["biomarkers"]).exists():
        biomarkers = Path(stats["biomarkers"]).read_text(encoding="utf-8")

    plan = state.get("artifacts", {}).get("supervisor_plan") or {
        "tasks": [{"name": t.get("name"), "agent": t.get("agent")} for t in state.get("tasks", [])]
    }

    key_paths = {
        "quality_report.html": str(outdir / "quality_report.html"),
        "taxonomy_profile.tsv": str(outdir / "taxonomy_profile.tsv"),
        "functional_profile.tsv": str(outdir / "functional_profile.tsv"),
        "diversity_analysis": str(outdir / "diversity_analysis"),
        "biomarkers": str(outdir / "biomarkers"),
        "literature_summary": str(outdir / "literature_summary"),
        "final_report.html": str(outdir / "final_report.html"),
    }

    html = HTML_TEMPLATE.render(
        query=state.get("user_query", ""),
        mode=state.get("mode", ""),
        critic_passed=bool(critic.get("passed", True)),
        critic_status="PASS" if critic.get("passed", True) else "WARNINGS",
        plan_source=state.get("artifacts", {}).get("plan_source", "n/a"),
        plan_json=json.dumps(plan, indent=2, ensure_ascii=False),
        biomarkers=biomarkers or "(none)",
        warnings=critic.get("warnings") or [],
        recommendations=critic.get("recommendations") or [],
        literature_html=_md_to_html(lit_md or "_No literature summary_"),
        interpretation_html=_md_to_html(interpretation),
        paths_json=json.dumps(key_paths, indent=2),
        plot_data=json.dumps(_plot_payload(state)),
    )

    final_html = outdir / "final_report.html"
    final_html.write_text(html, encoding="utf-8")

    # Also keep report/ subdir for backward compatibility
    report_dir = outdir / "report"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "report.html").write_text(html, encoding="utf-8")
    (report_dir / "interpretation.md").write_text(interpretation, encoding="utf-8")
    (report_dir / "methods.md").write_text(
        "# Methods\n\n"
        "Orchestrated by Metagenomic Research Agent (LangGraph).\n\n"
        "- QC: fastp (+ host filter)\n"
        "- Taxonomy: Kraken2/Bracken, MetaPhlAn4\n"
        "- Assembly: MEGAHIT → MetaBAT2 → GTDB-Tk (optional)\n"
        "- Function: KEGG/eggNOG/CAZy/CARD/VFDB\n"
        "- Statistics: Shannon, Bray-Curtis, fold-change biomarkers\n"
        "- Critic + Literature reasoning\n",
        encoding="utf-8",
    )
    reproduce = report_dir / "reproduce.sh"
    reproduce.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        f"meta-agent run --input {state.get('input_path')} --outdir {state.get('outdir')} "
        f"--mode {state.get('mode')} --yes "
        f"--query {json.dumps(state.get('user_query', ''))}\n",
        encoding="utf-8",
    )
    reproduce.chmod(0o755)

    (outdir / "paths.json").write_text(json.dumps(key_paths, indent=2), encoding="utf-8")
    return {
        "html": str(final_html),
        "legacy_html": str(report_dir / "report.html"),
        "methods": str(report_dir / "methods.md"),
        "reproduce": str(reproduce),
        "paths": str(outdir / "paths.json"),
    }


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    paths = generate(state)
    return {
        "report_path": paths["html"],
        "artifacts": {**state.get("artifacts", {}), "report": paths},
        "messages": state.get("messages", []) + [f"Report written to {paths['html']}"],
    }
