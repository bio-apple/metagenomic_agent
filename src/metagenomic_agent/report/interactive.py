"""Interactive Plotly analytics — composition, diversity, PCoA, heatmap with sig-filter."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


PALETTE = [
    "#1b9e77",
    "#d95f02",
    "#7570b3",
    "#e7298a",
    "#66a61e",
    "#e6ab02",
    "#a6761d",
    "#666666",
    "#1f78b4",
    "#b2df8a",
]


def _load_matrix(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))
    matrix: dict[str, dict[str, float]] = {}
    for row in rows:
        sid = row.get("sample") or row.get("sample_id")
        if not sid:
            continue
        matrix[sid] = {
            k: float(v) for k, v in row.items() if k not in {"sample", "sample_id"} and v not in {"", None}
        }
    return matrix


def _load_alpha(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                out.append(
                    {
                        "sample": row.get("sample") or row.get("sample_id"),
                        "group": row.get("group") or "unknown",
                        "shannon": float(row.get("shannon") or 0),
                        "richness": float(row.get("richness") or 0),
                    }
                )
            except ValueError:
                continue
    return out


def _load_beta_pairs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                out.append(
                    {
                        "sample_a": row.get("sample_a"),
                        "sample_b": row.get("sample_b"),
                        "bray_curtis": float(row.get("bray_curtis") or row.get("distance") or 0),
                    }
                )
            except ValueError:
                continue
    return out


def _load_biomarkers(path: Path, stats: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for b in stats.get("biomarker_list") or []:
        rows.append(
            {
                "genus": b.get("genus"),
                "log2fc": float(b.get("log2fc") or 0),
                "p_value": float(b.get("p_value") or 1),
                "q_value": float(b.get("q_value") if b.get("q_value") is not None else b.get("p_value") or 1),
                "direction": b.get("direction") or "",
            }
        )
    if rows:
        return rows
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                p = float(row.get("p_value") or 1)
                q = float(row.get("q_value") or p)
                rows.append(
                    {
                        "genus": row.get("genus"),
                        "log2fc": float(row.get("log2fc") or 0),
                        "p_value": p,
                        "q_value": q,
                        "direction": row.get("direction") or "",
                    }
                )
            except ValueError:
                continue
    return rows


def _fig_composition(matrix: dict[str, dict[str, float]], groups: dict[str, str], top_n: int = 12) -> dict:
    if not matrix:
        return {"data": [], "layout": {"title": "Species composition (no matrix)"}}
    totals: dict[str, float] = {}
    for ab in matrix.values():
        for g, v in ab.items():
            totals[g] = totals.get(g, 0.0) + float(v)
    top = [g for g, _ in sorted(totals.items(), key=lambda x: -x[1])[:top_n]]
    samples = sorted(matrix)
    traces = []
    for i, genus in enumerate(top):
        traces.append(
            {
                "type": "bar",
                "name": genus,
                "x": samples,
                "y": [matrix.get(s, {}).get(genus, 0.0) for s in samples],
                "marker": {"color": PALETTE[i % len(PALETTE)]},
                "hovertemplate": "%{x}<br>" + genus + ": %{y:.4f}<extra></extra>",
            }
        )
    # Other
    other = []
    for s in samples:
        known = sum(matrix.get(s, {}).get(g, 0.0) for g in top)
        total = sum(matrix.get(s, {}).values()) or 1.0
        other.append(max(total - known, 0.0))
    if any(v > 0 for v in other):
        traces.append(
            {
                "type": "bar",
                "name": "Other",
                "x": samples,
                "y": other,
                "marker": {"color": "#cccccc"},
            }
        )
    group_anno = ", ".join(f"{s}:{groups.get(s, '?')}" for s in samples[:8])
    return {
        "data": traces,
        "layout": {
            "title": "Taxonomic composition (stacked relative abundance)",
            "barmode": "stack",
            "yaxis": {"title": "Relative abundance", "tickformat": ".0%"},
            "xaxis": {"title": f"Samples ({group_anno}…)" if len(samples) > 8 else f"Samples ({group_anno})"},
            "legend": {"orientation": "h", "y": -0.2},
            "margin": {"t": 50, "b": 100},
            "hovermode": "closest",
        },
    }


def _fig_alpha_box(alpha_rows: list[dict[str, Any]]) -> dict:
    if not alpha_rows:
        return {"data": [], "layout": {"title": "Alpha diversity (no data)"}}
    by_group: dict[str, list[float]] = {}
    for r in alpha_rows:
        by_group.setdefault(r["group"], []).append(r["shannon"])
    traces = []
    for i, (g, vals) in enumerate(sorted(by_group.items())):
        traces.append(
            {
                "type": "box",
                "name": g,
                "y": vals,
                "boxpoints": "all",
                "jitter": 0.35,
                "pointpos": 0,
                "marker": {"color": PALETTE[i % len(PALETTE)]},
                "hovertemplate": f"{g}<br>Shannon=%{{y:.3f}}<extra></extra>",
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": "Alpha diversity (Shannon) by group",
            "yaxis": {"title": "Shannon index"},
            "boxmode": "group",
            "showlegend": False,
        },
    }


def _fig_beta_box(pairs: list[dict[str, Any]], groups: dict[str, str]) -> dict:
    if not pairs:
        return {"data": [], "layout": {"title": "Beta diversity (no pairwise distances)"}}
    within: list[float] = []
    between: list[float] = []
    for p in pairs:
        a, b = p.get("sample_a"), p.get("sample_b")
        if not a or not b:
            continue
        ga, gb = groups.get(a, "unknown"), groups.get(b, "unknown")
        d = p["bray_curtis"]
        if ga == gb:
            within.append(d)
        else:
            between.append(d)
    traces = []
    if within:
        traces.append(
            {
                "type": "box",
                "name": "Within-group",
                "y": within,
                "boxpoints": "all",
                "jitter": 0.3,
                "marker": {"color": PALETTE[0]},
            }
        )
    if between:
        traces.append(
            {
                "type": "box",
                "name": "Between-group",
                "y": between,
                "boxpoints": "all",
                "jitter": 0.3,
                "marker": {"color": PALETTE[1]},
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": "Beta diversity (Bray–Curtis) within vs between groups",
            "yaxis": {"title": "Bray–Curtis distance"},
            "showlegend": True,
        },
    }


def _fig_pcoa(pcoa: dict[str, Any]) -> dict:
    points = pcoa.get("points") or []
    if not points:
        return {"data": [], "layout": {"title": pcoa.get("title") or "PCoA (no points)"}}
    by_group: dict[str, list[dict[str, Any]]] = {}
    for p in points:
        by_group.setdefault(str(p.get("group") or "unknown"), []).append(p)
    ve = pcoa.get("variance_explained") or []
    pc1 = f"PC1 ({ve[0] * 100:.1f}%)" if ve else "PC1"
    pc2 = f"PC2 ({ve[1] * 100:.1f}%)" if len(ve) > 1 else "PC2"
    traces = []
    for i, (g, pts) in enumerate(sorted(by_group.items())):
        traces.append(
            {
                "type": "scatter",
                "mode": "markers+text",
                "name": g,
                "x": [p.get("PC1") for p in pts],
                "y": [p.get("PC2") for p in pts],
                "text": [p.get("sample") for p in pts],
                "textposition": "top center",
                "marker": {"size": 12, "color": PALETTE[i % len(PALETTE)]},
                "hovertemplate": "%{text}<br>group=" + g + "<br>PC1=%{x:.3f}<br>PC2=%{y:.3f}<extra></extra>",
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": pcoa.get("title") or "PCoA (classical MDS on Bray–Curtis)",
            "xaxis": {"title": pc1, "zeroline": True},
            "yaxis": {"title": pc2, "zeroline": True},
            "hovermode": "closest",
        },
    }


def _heatmap_payload(
    matrix: dict[str, dict[str, float]],
    biomarkers: list[dict[str, Any]],
    q_cut: float,
    top_n: int = 25,
) -> dict[str, Any]:
    sig = [b for b in biomarkers if b.get("genus") and float(b.get("q_value", 1)) <= q_cut]
    sig.sort(key=lambda b: float(b.get("q_value", 1)))
    genera = [b["genus"] for b in sig[:top_n]]
    if not genera:
        # fallback: top variance / abundance genera
        totals: dict[str, float] = {}
        for ab in matrix.values():
            for g, v in ab.items():
                totals[g] = totals.get(g, 0.0) + float(v)
        genera = [g for g, _ in sorted(totals.items(), key=lambda x: -x[1])[:top_n]]
    samples = sorted(matrix)
    z = [[matrix.get(s, {}).get(g, 0.0) for s in samples] for g in genera]
    q_map = {b["genus"]: b.get("q_value") for b in biomarkers}
    return {
        "genera": genera,
        "samples": samples,
        "z": z,
        "q_map": q_map,
        "n_sig": len(sig),
        "q_cut": q_cut,
    }


def _fig_heatmap(payload: dict[str, Any]) -> dict:
    if not payload.get("genera"):
        return {"data": [], "layout": {"title": "Heatmap (no taxa)"}}
    return {
        "data": [
            {
                "type": "heatmap",
                "z": payload["z"],
                "x": payload["samples"],
                "y": payload["genera"],
                "colorscale": "Viridis",
                "hoverongaps": False,
                "colorbar": {"title": "rel. abund."},
                "hovertemplate": "sample=%{x}<br>taxon=%{y}<br>abund=%{z:.4f}<extra></extra>",
            }
        ],
        "layout": {
            "title": (
                f"Taxon heatmap (q≤{payload['q_cut']}; {payload['n_sig']} significant → "
                f"showing {len(payload['genera'])})"
            ),
            "xaxis": {"title": "Sample"},
            "yaxis": {"title": "Genus", "autorange": "reversed"},
            "margin": {"l": 120},
        },
    }


def _fig_volcano(biomarkers: list[dict[str, Any]], q_cut: float = 0.05) -> dict:
    if not biomarkers:
        return {"data": [], "layout": {"title": "Volcano (no biomarkers)"}}
    x, y, text, colors = [], [], [], []
    for b in biomarkers:
        p = max(float(b.get("p_value") or 1), 1e-300)
        q = float(b.get("q_value") or p)
        x.append(float(b.get("log2fc") or 0))
        y.append(-math.log10(p))
        text.append(f"{b.get('genus')}<br>q={q:.3g}")
        colors.append("#d95f02" if q <= q_cut else "#999999")
    return {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "x": x,
                "y": y,
                "text": text,
                "marker": {"color": colors, "size": 10},
                "hovertemplate": "%{text}<br>log2FC=%{x:.2f}<br>-log10p=%{y:.2f}<extra></extra>",
            }
        ],
        "layout": {
            "title": f"Volcano plot (orange = q≤{q_cut})",
            "xaxis": {"title": "log2 fold-change"},
            "yaxis": {"title": "−log10(p)"},
            "hovermode": "closest",
        },
    }


def build_interactive_figures(state: dict[str, Any], *, default_q: float = 0.1) -> dict[str, Any]:
    """Build Plotly figure specs + filter metadata for interactive dashboard."""
    outdir = Path(state["outdir"])
    stats = state.get("artifacts", {}).get("statistics") or state.get("statistics") or {}
    groups = stats.get("groups") or {
        s["sample_id"]: s.get("group") or "unknown" for s in state.get("samples") or []
    }

    mat_path = Path(stats.get("genus_matrix") or outdir / "diversity_analysis" / "genus_matrix.tsv")
    matrix = _load_matrix(mat_path)
    if not matrix:
        tax = (state.get("artifacts") or {}).get("taxonomy") or {}
        for sid, art in tax.items():
            for g in art.get("top_genera") or []:
                matrix.setdefault(sid, {})[g] = matrix.get(sid, {}).get(g, 0.0) + 0.1

    alpha_rows = _load_alpha(Path(stats.get("alpha_diversity") or outdir / "diversity_analysis" / "alpha_diversity.tsv"))
    beta_pairs = _load_beta_pairs(Path(stats.get("beta_diversity") or outdir / "diversity_analysis" / "beta_diversity.tsv"))
    bio_path = Path(stats.get("biomarkers") or outdir / "biomarkers" / "biomarkers.tsv")
    biomarkers = _load_biomarkers(bio_path, stats)

    pcoa_path = outdir / "report" / "figures" / "pcoa.json"
    pcoa = json.loads(pcoa_path.read_text(encoding="utf-8")) if pcoa_path.exists() else {"points": []}

    # Precompute heatmaps at several q cuts for JS slider
    q_cuts = [0.01, 0.05, 0.1, 0.2, 1.0]
    heat_by_q = {str(q): _heatmap_payload(matrix, biomarkers, q_cut=q) for q in q_cuts}
    heat0 = heat_by_q.get(str(default_q)) or heat_by_q["0.1"]

    figures = {
        "composition": _fig_composition(matrix, groups),
        "alpha_box": _fig_alpha_box(alpha_rows),
        "beta_box": _fig_beta_box(beta_pairs, groups),
        "pcoa": _fig_pcoa(pcoa),
        "heatmap": _fig_heatmap(heat0),
        "volcano": _fig_volcano(biomarkers, q_cut=default_q),
    }
    return {
        "figures": figures,
        "heatmap_by_q": heat_by_q,
        "biomarkers": biomarkers,
        "default_q": default_q,
        "groups": groups,
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Interactive Metagenomic Analytics</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    :root {
      --ink: #14241e;
      --muted: #4a6358;
      --bg: #eef3f0;
      --card: #ffffff;
      --accent: #1b9e77;
      --line: #d5e0da;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif;
      background: linear-gradient(160deg, #e8f0eb 0%, #f7f5ef 45%, #eef3f0 100%);
      color: var(--ink);
    }
    header {
      padding: 1.4rem 1.6rem 0.6rem;
      border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,.72);
      backdrop-filter: blur(8px);
      position: sticky; top: 0; z-index: 5;
    }
    h1 { margin: 0; font-size: 1.45rem; letter-spacing: -.02em; }
    .sub { color: var(--muted); margin: .35rem 0 0; font-size: .92rem; }
    .controls {
      display: flex; flex-wrap: wrap; gap: .75rem 1.2rem; align-items: center;
      padding: .85rem 1.6rem 1rem;
    }
    .tabs { display: flex; flex-wrap: wrap; gap: .4rem; }
    .tab {
      border: 1px solid var(--line); background: var(--card); color: var(--ink);
      padding: .4rem .8rem; border-radius: 999px; cursor: pointer; font-size: .88rem;
    }
    .tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    label { font-size: .88rem; color: var(--muted); display: flex; align-items: center; gap: .5rem; }
    input[type=range] { width: 160px; }
    main { padding: 0 1.2rem 2rem; }
    .panel { display: none; background: var(--card); border-radius: 12px;
      box-shadow: 0 1px 6px rgba(20,36,30,.07); padding: .6rem; min-height: 480px; }
    .panel.active { display: block; }
    .plot { width: 100%; height: 520px; }
    .hint { color: var(--muted); font-size: .85rem; padding: 0 .4rem .4rem; }
  </style>
</head>
<body>
  <header>
    <h1>Interactive Metagenomic Analytics</h1>
    <p class="sub">{{ query }} · run_id={{ run_id }} · 拖拽缩放 / 图例点击筛选 · Heatmap 可按 FDR q 过滤显著差异菌群</p>
  </header>
  <div class="controls">
    <div class="tabs" id="tabs">
      <button class="tab active" data-panel="composition">物种组成</button>
      <button class="tab" data-panel="alpha">Alpha 箱线</button>
      <button class="tab" data-panel="beta">Beta 箱线</button>
      <button class="tab" data-panel="pcoa">PCoA</button>
      <button class="tab" data-panel="heatmap">Heatmap</button>
      <button class="tab" data-panel="volcano">Volcano</button>
    </div>
    <label>FDR q ≤ <span id="qLabel">{{ default_q }}</span>
      <input id="qSlider" type="range" min="0" max="4" step="1" value="{{ q_index }}"/>
    </label>
  </div>
  <main>
    <section class="panel active" id="panel-composition">
      <p class="hint">堆叠柱状图：样本物种相对丰度组成，点击图例可隐藏/显示分类单元。</p>
      <div class="plot" id="plot-composition"></div>
    </section>
    <section class="panel" id="panel-alpha">
      <p class="hint">Shannon 指数按分组的箱线图（含散点）。</p>
      <div class="plot" id="plot-alpha"></div>
    </section>
    <section class="panel" id="panel-beta">
      <p class="hint">Bray–Curtis：组内 vs 组间距离分布。</p>
      <div class="plot" id="plot-beta"></div>
    </section>
    <section class="panel" id="panel-pcoa">
      <p class="hint">PCoA（经典 MDS）；悬停查看样本，滚轮缩放。</p>
      <div class="plot" id="plot-pcoa"></div>
    </section>
    <section class="panel" id="panel-heatmap">
      <p class="hint">显著差异菌群热图：调节上方 q 阈值实时筛选；橙色 volcano 点同步高亮阈值。</p>
      <div class="plot" id="plot-heatmap"></div>
    </section>
    <section class="panel" id="panel-volcano">
      <p class="hint">log2FC vs −log10(p)；橙色为当前 q 阈值下显著。</p>
      <div class="plot" id="plot-volcano"></div>
    </section>
  </main>
  <script>
    const FIGS = {{ figures_json | safe }};
    const HEAT_BY_Q = {{ heatmap_by_q_json | safe }};
    const Q_CUTS = {{ q_cuts_json | safe }};
    const BIO = {{ biomarkers_json | safe }};

    function heatFig(q) {
      const key = String(q);
      const payload = HEAT_BY_Q[key] || HEAT_BY_Q["0.1"];
      return {
        data: [{
          type: "heatmap",
          z: payload.z,
          x: payload.samples,
          y: payload.genera,
          colorscale: "Viridis",
          colorbar: {title: "rel. abund."},
          hovertemplate: "sample=%{x}<br>taxon=%{y}<br>abund=%{z:.4f}<extra></extra>"
        }],
        layout: Object.assign({}, FIGS.heatmap.layout, {
          title: `Taxon heatmap (q≤${payload.q_cut}; ${payload.n_sig} significant → showing ${payload.genera.length})`
        })
      };
    }

    function volcanoFig(q) {
      const x = [], y = [], text = [], colors = [];
      for (const b of BIO) {
        const p = Math.max(Number(b.p_value || 1), 1e-300);
        const qq = Number(b.q_value != null ? b.q_value : p);
        x.push(Number(b.log2fc || 0));
        y.push(-Math.log10(p));
        text.push(`${b.genus}<br>q=${qq}`);
        colors.push(qq <= q ? "#d95f02" : "#999999");
      }
      return {
        data: [{
          type: "scatter", mode: "markers", x, y, text,
          marker: {color: colors, size: 10},
          hovertemplate: "%{text}<br>log2FC=%{x:.2f}<br>-log10p=%{y:.2f}<extra></extra>"
        }],
        layout: Object.assign({}, FIGS.volcano.layout, {title: `Volcano plot (orange = q≤${q})`})
      };
    }

    const cfg = {responsive: true, displaylogo: false};
    Plotly.newPlot("plot-composition", FIGS.composition.data, FIGS.composition.layout, cfg);
    Plotly.newPlot("plot-alpha", FIGS.alpha_box.data, FIGS.alpha_box.layout, cfg);
    Plotly.newPlot("plot-beta", FIGS.beta_box.data, FIGS.beta_box.layout, cfg);
    Plotly.newPlot("plot-pcoa", FIGS.pcoa.data, FIGS.pcoa.layout, cfg);
    const h0 = heatFig(Q_CUTS[{{ q_index }}]);
    Plotly.newPlot("plot-heatmap", h0.data, h0.layout, cfg);
    const v0 = volcanoFig(Q_CUTS[{{ q_index }}]);
    Plotly.newPlot("plot-volcano", v0.data, v0.layout, cfg);

    document.querySelectorAll(".tab").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById("panel-" + btn.dataset.panel).classList.add("active");
        window.dispatchEvent(new Event("resize"));
      });
    });

    const slider = document.getElementById("qSlider");
    const qLabel = document.getElementById("qLabel");
    slider.addEventListener("input", () => {
      const q = Q_CUTS[Number(slider.value)];
      qLabel.textContent = q;
      const h = heatFig(q);
      Plotly.react("plot-heatmap", h.data, h.layout, cfg);
      const v = volcanoFig(q);
      Plotly.react("plot-volcano", v.data, v.layout, cfg);
    });
  </script>
</body>
</html>
"""


def write_interactive_dashboard(state: dict[str, Any], *, default_q: float = 0.1) -> dict[str, str]:
    """Write Plotly JSON on disk + lightweight dashboard that loads figures on demand."""
    from jinja2 import Template

    viz_cfg = ((state.get("config") or {}).get("visualization") or {})
    lite = bool(viz_cfg.get("lite", True))
    max_biomarkers = int(viz_cfg.get("max_inline_biomarkers", 50))

    payload = build_interactive_figures(state, default_q=default_q)
    outdir = Path(state["outdir"])
    fig_dir = outdir / "report" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    figures = payload["figures"]
    for name, fig in figures.items():
        (fig_dir / f"{name}.plotly.json").write_text(
            json.dumps(fig, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    (fig_dir / "heatmap_by_q.json").write_text(
        json.dumps(payload["heatmap_by_q"], ensure_ascii=False), encoding="utf-8"
    )
    bios = payload["biomarkers"][:max_biomarkers]
    (fig_dir / "biomarkers_lite.json").write_text(json.dumps(bios, ensure_ascii=False), encoding="utf-8")

    # Summary-only sidecar for huge cohorts
    summary = {
        "n_samples": len(payload.get("groups") or {}),
        "n_biomarkers_total": len(payload["biomarkers"]),
        "n_biomarkers_shown": len(bios),
        "default_q": default_q,
        "tables": {
            "genus_matrix": "diversity_analysis/genus_matrix.tsv",
            "biomarkers": "biomarkers/biomarkers.tsv",
            "alpha": "diversity_analysis/alpha_diversity.tsv",
        },
        "plotly": {k: f"report/figures/{k}.plotly.json" for k in figures},
        "policy": "lite_metadata_plus_ondemand_json",
    }
    (fig_dir / "dashboard_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    q_cuts = [0.01, 0.05, 0.1, 0.2, 1.0]
    try:
        q_index = q_cuts.index(default_q)
    except ValueError:
        q_index = 2

    if lite:
        html = Template(DASHBOARD_LITE_HTML).render(
            query=state.get("user_query") or "",
            run_id=state.get("run_id") or "",
            default_q=default_q,
            q_index=q_index,
            q_cuts_json=json.dumps(q_cuts),
            summary_json=json.dumps(summary, ensure_ascii=False),
            figures_base="report/figures",
        )
    else:
        html = Template(DASHBOARD_HTML).render(
            query=state.get("user_query") or "",
            run_id=state.get("run_id") or "",
            default_q=default_q,
            q_index=q_index,
            figures_json=json.dumps(figures, ensure_ascii=False),
            heatmap_by_q_json=json.dumps(payload["heatmap_by_q"], ensure_ascii=False),
            q_cuts_json=json.dumps(q_cuts),
            biomarkers_json=json.dumps(bios, ensure_ascii=False),
        )

    dash_path = fig_dir / "interactive_dashboard.html"
    dash_path.write_text(html, encoding="utf-8")
    root_dash = outdir / "interactive_dashboard.html"
    # Root copy must use relative paths into report/figures — rewrite base for root
    if lite:
        root_html = Template(DASHBOARD_LITE_HTML).render(
            query=state.get("user_query") or "",
            run_id=state.get("run_id") or "",
            default_q=default_q,
            q_index=q_index,
            q_cuts_json=json.dumps(q_cuts),
            summary_json=json.dumps(summary, ensure_ascii=False),
            figures_base="report/figures",
        )
        root_dash.write_text(root_html, encoding="utf-8")
    else:
        root_dash.write_text(html, encoding="utf-8")

    index = {
        "dashboard": str(dash_path.relative_to(outdir)),
        "dashboard_root": "interactive_dashboard.html",
        "mode": "lite" if lite else "embedded",
        "plotly_json": [f"report/figures/{k}.plotly.json" for k in figures],
        "summary": "report/figures/dashboard_summary.json",
        "default_q": default_q,
        "n_biomarkers": len(payload["biomarkers"]),
    }
    (fig_dir / "interactive_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return {
        "dashboard": str(dash_path),
        "dashboard_root": str(root_dash),
        "index": str(fig_dir / "interactive_index.json"),
        "mode": "lite" if lite else "embedded",
    }


DASHBOARD_LITE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Interactive Metagenomic Analytics (lite)</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    body { margin:0; font-family:"IBM Plex Sans","Noto Sans SC",sans-serif; background:#eef3f0; color:#14241e; }
    header { padding:1.2rem 1.4rem; background:rgba(255,255,255,.85); border-bottom:1px solid #d5e0da; position:sticky; top:0; }
    h1 { margin:0; font-size:1.35rem; }
    .sub { color:#4a6358; margin:.35rem 0 0; font-size:.9rem; }
    .controls { display:flex; flex-wrap:wrap; gap:.6rem 1rem; padding:.8rem 1.4rem; align-items:center; }
    .tab { border:1px solid #d5e0da; background:#fff; padding:.35rem .75rem; border-radius:999px; cursor:pointer; }
    .tab.active { background:#1b9e77; color:#fff; border-color:#1b9e77; }
    main { padding:0 1.2rem 2rem; }
    .panel { display:none; background:#fff; border-radius:12px; padding:.6rem; min-height:420px; }
    .panel.active { display:block; }
    .plot { width:100%; height:480px; }
    .hint { color:#4a6358; font-size:.85rem; }
    a { color:#0f766e; }
    #summaryBox { background:#fff; margin:0 1.2rem 1rem; padding:1rem 1.2rem; border-radius:12px; }
  </style>
</head>
<body>
  <header>
    <h1>Interactive Analytics <small style="font-weight:400;color:#4a6358">(lite / on-demand)</small></h1>
    <p class="sub">{{ query }} · run_id={{ run_id }} · 默认仅摘要；图按需 fetch JSON，完整表走下载链接</p>
  </header>
  <div id="summaryBox"><pre id="summaryPre">Loading summary…</pre></div>
  <div class="controls">
    <div class="tabs" id="tabs">
      <button class="tab active" data-panel="composition">组成</button>
      <button class="tab" data-panel="alpha">Alpha</button>
      <button class="tab" data-panel="beta">Beta</button>
      <button class="tab" data-panel="pcoa">PCoA</button>
      <button class="tab" data-panel="heatmap">Heatmap</button>
      <button class="tab" data-panel="volcano">Volcano</button>
    </div>
    <label>FDR q ≤ <span id="qLabel">{{ default_q }}</span>
      <input id="qSlider" type="range" min="0" max="4" step="1" value="{{ q_index }}"/>
    </label>
  </div>
  <main>
    <section class="panel active" id="panel-composition"><p class="hint">按需加载 composition.plotly.json</p><div class="plot" id="plot-composition"></div></section>
    <section class="panel" id="panel-alpha"><div class="plot" id="plot-alpha"></div></section>
    <section class="panel" id="panel-beta"><div class="plot" id="plot-beta"></div></section>
    <section class="panel" id="panel-pcoa"><div class="plot" id="plot-pcoa"></div></section>
    <section class="panel" id="panel-heatmap"><div class="plot" id="plot-heatmap"></div></section>
    <section class="panel" id="panel-volcano"><div class="plot" id="plot-volcano"></div></section>
  </main>
  <script>
    const BASE = "{{ figures_base }}";
    const Q_CUTS = {{ q_cuts_json | safe }};
    const SUMMARY = {{ summary_json | safe }};
    const cfg = {responsive:true, displaylogo:false};
    const cache = {};
    document.getElementById("summaryPre").textContent =
      `samples=${SUMMARY.n_samples} biomarkers=${SUMMARY.n_biomarkers_total} (inline cap ${SUMMARY.n_biomarkers_shown})\\n` +
      `tables: ${SUMMARY.tables.genus_matrix} | ${SUMMARY.tables.biomarkers}\\n` +
      `policy: ${SUMMARY.policy}`;

    async function loadFig(name) {
      if (cache[name]) return cache[name];
      const resp = await fetch(`${BASE}/${name}.plotly.json`);
      const fig = await resp.json();
      cache[name] = fig;
      return fig;
    }
    async function draw(id, name) {
      const fig = await loadFig(name);
      Plotly.newPlot(id, fig.data || [], fig.layout || {}, cfg);
    }
    async function drawHeat(q) {
      const resp = await fetch(`${BASE}/heatmap_by_q.json`);
      const byq = await resp.json();
      const payload = byq[String(q)] || byq["0.1"];
      const layout = Object.assign({}, (await loadFig("heatmap")).layout || {}, {
        title: `Taxon heatmap (q≤${payload.q_cut}; ${payload.n_sig} sig → ${payload.genera.length})`
      });
      Plotly.react("plot-heatmap", [{
        type:"heatmap", z:payload.z, x:payload.samples, y:payload.genera, colorscale:"Viridis",
        colorbar:{title:"rel. abund."}
      }], layout, cfg);
    }
    async function drawVolcano(q) {
      const resp = await fetch(`${BASE}/biomarkers_lite.json`);
      const BIO = await resp.json();
      const x=[], y=[], text=[], colors=[];
      for (const b of BIO) {
        const p = Math.max(Number(b.p_value||1), 1e-300);
        const qq = Number(b.q_value != null ? b.q_value : p);
        x.push(Number(b.log2fc||0)); y.push(-Math.log10(p));
        text.push(`${b.genus}<br>q=${qq}`);
        colors.push(qq <= q ? "#d95f02" : "#999999");
      }
      Plotly.react("plot-volcano", [{
        type:"scatter", mode:"markers", x,y,text, marker:{color:colors, size:10}
      }], {title:`Volcano (orange = q≤${q})`, xaxis:{title:"log2FC"}, yaxis:{title:"-log10p"}}, cfg);
    }

    // Lazy: load active tab only
    draw("plot-composition", "composition");
    document.querySelectorAll(".tab").forEach(btn => {
      btn.addEventListener("click", async () => {
        document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        const name = btn.dataset.panel;
        document.getElementById("panel-" + name).classList.add("active");
        const map = {composition:"composition", alpha:"alpha_box", beta:"beta_box", pcoa:"pcoa", heatmap:"heatmap", volcano:"volcano"};
        if (name === "heatmap") await drawHeat(Q_CUTS[Number(document.getElementById("qSlider").value)]);
        else if (name === "volcano") await drawVolcano(Q_CUTS[Number(document.getElementById("qSlider").value)]);
        else await draw("plot-" + name, map[name]);
      });
    });
    document.getElementById("qSlider").addEventListener("input", async () => {
      const q = Q_CUTS[Number(document.getElementById("qSlider").value)];
      document.getElementById("qLabel").textContent = q;
      const active = document.querySelector(".tab.active").dataset.panel;
      if (active === "heatmap") await drawHeat(q);
      if (active === "volcano") await drawVolcano(q);
    });
  </script>
</body>
</html>
"""
