"""Report Generator — final scientific HTML report and path packing."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from jinja2 import Template

from metagenomic_agent.report.interpreter import interpret


def shlex_quote(s: str) -> str:
    return shlex.quote(s)

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
    .plot { height: 420px; width: 100%; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    @media (max-width: 900px) { .grid2 { grid-template-columns: 1fr; } }
    a.btn { display: inline-block; margin-top: .5rem; padding: .45rem .9rem; background: #1b9e77; color: #fff;
            text-decoration: none; border-radius: 8px; font-size: .9rem; }
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
    <h2>Interactive Analytics</h2>
    <p>物种组成、Alpha/Beta 箱线图、PCoA、显著差异菌群 Heatmap（可按 FDR q 筛选）。</p>
    <a class="btn" href="{{ dashboard_href }}" target="_blank" rel="noopener">打开交互式仪表盘</a>
  </div>

  <div class="card">
    <h2>Supervisor Plan</h2>
    <pre>{{ plan_json }}</pre>
  </div>

  <div class="card">
    <h2>Taxonomic Composition</h2>
    <div id="plot-composition" class="plot"></div>
  </div>

  <div class="card">
    <h2>Diversity &amp; Ordination</h2>
    <div class="grid2">
      <div id="plot-alpha" class="plot"></div>
      <div id="plot-beta" class="plot"></div>
    </div>
    <div id="plot-pcoa" class="plot" style="margin-top:1rem;"></div>
  </div>

  <div class="card">
    <h2>Significant Taxa Heatmap &amp; Volcano</h2>
    <div class="grid2">
      <div id="plot-heatmap" class="plot"></div>
      <div id="plot-volcano" class="plot"></div>
    </div>
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
    <h2>Data Quality Scores</h2>
    <pre>{{ quality_json }}</pre>
  </div>

  <div class="card">
    <h2>Evidence Table</h2>
    <div>{{ evidence_html | safe }}</div>
  </div>

  <div class="card">
    <h2>Evidence Chains（抗幻觉）</h2>
    <div>{{ claims_html | safe }}</div>
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
    var FIGS = {{ interactive_figs | safe }};
    var cfg = {responsive: true, displaylogo: false};
    function draw(id, key) {
      var f = FIGS[key] || {data: [], layout: {title: key}};
      Plotly.newPlot(id, f.data || [], f.layout || {}, cfg);
    }
    draw('plot-composition', 'composition');
    draw('plot-alpha', 'alpha_box');
    draw('plot-beta', 'beta_box');
    draw('plot-pcoa', 'pcoa');
    draw('plot-heatmap', 'heatmap');
    draw('plot-volcano', 'volcano');
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

    evidence_md = ""
    ev_path = Path(state["outdir"]) / "evidence" / "evidence_table.md"
    if ev_path.exists():
        evidence_md = ev_path.read_text(encoding="utf-8")

    claims_md = ""
    claims_path = Path(state["outdir"]) / "evidence" / "claims.md"
    if claims_path.exists():
        claims_md = claims_path.read_text(encoding="utf-8")

    quality = (state.get("artifacts") or {}).get("quality_scores") or {}

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
        "evidence": str(outdir / "evidence"),
        "context_summary": str(outdir / "context" / "pipeline_summary.json"),
        "reproducible_nf": str(outdir / "workflow" / "reproducible.nf"),
        "reproducible_smk": str(outdir / "workflow" / "reproducible.smk"),
        "seeds": str(outdir / "workflow" / "seeds.json"),
        "quality": str(outdir / "quality"),
        "workflow_dag": str(outdir / "workflow" / "dag.json"),
        "manuscript": str(outdir / "report" / "manuscript"),
        "figures": str(outdir / "report" / "figures"),
        "interactive_dashboard": str(outdir / "interactive_dashboard.html"),
        "xai": str(outdir / "xai"),
        "router": str(outdir / "router_decision.json"),
        "tool_specialist": str(outdir / "tool_specialist"),
        "reproducibility": str(outdir / "reproducibility"),
        "final_report.html": str(outdir / "final_report.html"),
    }

    from metagenomic_agent.report.interactive import build_interactive_figures, write_interactive_dashboard

    dash = outdir / "interactive_dashboard.html"
    if not dash.exists():
        write_interactive_dashboard(state)
    figs_payload = build_interactive_figures(state)
    interactive_figs = figs_payload["figures"]

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
        quality_json=json.dumps(quality.get("scores") or quality, indent=2, ensure_ascii=False),
        evidence_html=_md_to_html(evidence_md or "_No evidence table_"),
        claims_html=_md_to_html(claims_md or "_No evidence chains (run literature/report)_"),
        literature_html=_md_to_html(lit_md or "_No literature summary_"),
        interpretation_html=_md_to_html(interpretation),
        paths_json=json.dumps(key_paths, indent=2),
        dashboard_href="interactive_dashboard.html",
        interactive_figs=json.dumps(interactive_figs, ensure_ascii=False),
    )

    final_html = outdir / "final_report.html"
    final_html.write_text(html, encoding="utf-8")

    # Also keep report/ subdir for backward compatibility
    report_dir = outdir / "report"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "report.html").write_text(html, encoding="utf-8")
    (report_dir / "interpretation.md").write_text(interpretation, encoding="utf-8")

    from metagenomic_agent import __version__

    dag = state.get("dag") or []
    dag_lines = "\n".join(
        f"- `{n.get('id')}` → agent=`{n.get('agent')}` tools={n.get('tools')} status={n.get('status')}"
        for n in dag
    ) or "- (empty)"
    stats_methods = (stats.get("methods") if isinstance(stats, dict) else None) or []
    self_heal = (state.get("artifacts") or {}).get("self_heal_actions") or []
    methods_md = (
        f"# Methods\n\n"
        f"Software: metagenomic-agent **v{__version__}**  \n"
        f"Mode: `{state.get('mode')}`  \n"
        f"Plan source: `{state.get('artifacts', {}).get('plan_source', 'n/a')}`  \n"
        f"Run id: `{state.get('run_id', 'n/a')}`\n\n"
        f"## Executed DAG\n\n{dag_lines}\n\n"
        f"## Analytical methods (as run)\n\n"
        f"- QC: fastp; host removal: Bowtie2/Kneaddata when configured\n"
        f"- Taxonomy: Kraken2/Bracken and/or MetaPhlAn\n"
        f"- Assembly/MAGs (if planned): MEGAHIT or metaSPAdes → MetaBAT2/MaxBin2 → DAS-Tool-style consensus → CheckM2 → GTDB-Tk\n"
        f"- Function: DIAMOND / profile tables (KEGG/eggNOG/CAZy/CARD/VFDB labels)\n"
        f"- Statistics: {', '.join(stats_methods) if stats_methods else 'shannon / bray-curtis / Mann-Whitney U + BH-FDR'}\n"
        f"- Self-heal actions: {self_heal or 'none'}\n\n"
        f"## Limitations (honest reporting)\n\n"
        f"- Default differential abundance is Mann-Whitney U + Benjamini–Hochberg FDR; "
        f"for journal submission prefer ANCOM-BC / MaAsLin2 / LEfSe on exported tables.\n"
        f"- Nextflow/Snakemake configs are generated for handoff; primary orchestration is LangGraph unless "
        f"`execution.engine` is set and the binary is available.\n"
        f"- Mock mode synthesizes tool outputs for software demos and CI — do not treat mock abundances as biological truth.\n"
    )
    (report_dir / "methods.md").write_text(methods_md, encoding="utf-8")

    from metagenomic_agent.report.manuscript import write_manuscript

    ms_template = ((state.get("config") or {}).get("report") or {}).get("manuscript_template", "Microbiome")
    manuscript_paths = write_manuscript(state, template=ms_template)

    meta = state.get("metadata_path")
    reproduce = report_dir / "reproduce.sh"
    reproduce.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        f"# metagenomic-agent v{__version__} run_id={state.get('run_id', '')}\n"
        f"meta-agent run \\\n"
        f"  --input {shlex_quote(str(state.get('input_path')))} \\\n"
        f"  --outdir {shlex_quote(str(state.get('outdir')))} \\\n"
        f"  --mode {shlex_quote(str(state.get('mode')))} \\\n"
        f"  --query {shlex_quote(str(state.get('user_query', '')))} \\\n"
        + (f"  --metadata {shlex_quote(str(meta))} \\\n" if meta else "")
        + "  --yes\n",
        encoding="utf-8",
    )
    reproduce.chmod(0o755)

    (outdir / "paths.json").write_text(json.dumps(key_paths, indent=2), encoding="utf-8")
    return {
        "html": str(final_html),
        "legacy_html": str(report_dir / "report.html"),
        "methods": str(report_dir / "methods.md"),
        "reproduce": str(reproduce),
        "manuscript": manuscript_paths.get("combined", ""),
        "paths": str(outdir / "paths.json"),
    }


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    from metagenomic_agent.coordinator.summary import write_pipeline_summary
    from metagenomic_agent.report.reproducibility import write_reproducibility_bundle

    arts0 = dict(state.get("artifacts") or {})
    if arts0.get("hold_report") or arts0.get("report_publish_confirmed") is False:
        hold_note = Path(state["outdir"]) / "report" / "HELD.md"
        hold_note.parent.mkdir(parents=True, exist_ok=True)
        hold_note.write_text(
            "# Report held by HITL\n\n"
            "Analyst chose to defer final report generation (`hold_report`).\n"
            "Resume after approving `confirm_report_publish` (A=shareable or B=draft).\n",
            encoding="utf-8",
        )
        return {
            "report_path": None,
            "artifacts": {**arts0, "report_held": str(hold_note)},
            "messages": state.get("messages", [])
            + [f"Report held by HITL — see {hold_note}"],
        }

    # Ensure latest metadata summary before packaging
    if ((state.get("config") or {}).get("summary") or {}).get("enabled", True):
        summary_full = write_pipeline_summary(state)
        llm_ctx = summary_full.pop("_llm_context", "")
        arts0["pipeline_summary"] = {k: v for k, v in summary_full.items() if not k.startswith("_")}
        arts0["llm_context"] = llm_ctx
        state = {**state, "artifacts": arts0}

    paths = generate(state)
    bundle = write_reproducibility_bundle(state)
    from metagenomic_agent.knowledge.reasoning_log import finalize_reasoning, log_decision

    shareable = bool(arts0.get("report_shareable")) or bool(
        ((state.get("config") or {}).get("report") or {}).get("shareable")
    )
    state = {**state, "artifacts": {**arts0, **(state.get("artifacts") or {})}}
    reason_patch = log_decision(
        state,
        "report",
        "Finalize HTML report + reproducibility bundle",
        f"shareable={shareable}; html={paths.get('html')}",
    )
    finalized = finalize_reasoning({**state, **reason_patch, "artifacts": {**(state.get("artifacts") or {}), **(reason_patch.get("artifacts") or {})}})
    arts = {
        **state.get("artifacts", {}),
        **(reason_patch.get("artifacts") or {}),
        **(finalized.get("artifacts") or {}),
        "report": paths,
        "reproducibility": bundle,
        "report_shareable": shareable,
    }
    share_msg = "shareable" if shareable else "internal draft (not marked for external share)"
    return {
        "report_path": paths["html"],
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [
            f"Report written to {paths['html']} ({share_msg})",
            f"Reproducibility bundle: {bundle.get('manifest')}",
            f"Workflows: {bundle.get('reproducible_nf')} / {bundle.get('reproducible_smk')} seed={bundle.get('run_seed')}",
            f"Reasoning chain: {arts.get('reasoning_md')}",
        ],
    }
