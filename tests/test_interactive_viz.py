"""Interactive Plotly dashboard tests."""

from __future__ import annotations

import json
from pathlib import Path

from metagenomic_agent.report.interactive import (
    build_interactive_figures,
    write_interactive_dashboard,
)


def _demo_state(tmp_path: Path) -> dict:
    div = tmp_path / "diversity_analysis"
    bio = tmp_path / "biomarkers"
    fig = tmp_path / "report" / "figures"
    div.mkdir(parents=True)
    bio.mkdir(parents=True)
    fig.mkdir(parents=True)

    (div / "genus_matrix.tsv").write_text(
        "sample\tFaecalibacterium\tEscherichia\tBacteroides\n"
        "c1\t0.25\t0.05\t0.30\n"
        "c2\t0.22\t0.06\t0.28\n"
        "i1\t0.08\t0.20\t0.25\n"
        "i2\t0.07\t0.22\t0.24\n",
        encoding="utf-8",
    )
    (div / "alpha_diversity.tsv").write_text(
        "sample\tgroup\tshannon\trichness\n"
        "c1\tControl\t3.1\t40\n"
        "c2\tControl\t3.0\t38\n"
        "i1\tIBD\t2.2\t30\n"
        "i2\tIBD\t2.1\t28\n",
        encoding="utf-8",
    )
    (div / "beta_diversity.tsv").write_text(
        "sample_a\tsample_b\tbray_curtis\n"
        "c1\tc2\t0.15\n"
        "i1\ti2\t0.18\n"
        "c1\ti1\t0.45\n"
        "c2\ti2\t0.50\n",
        encoding="utf-8",
    )
    (bio / "biomarkers.tsv").write_text(
        "genus\tgroup_a\tgroup_b\tmean_a\tmean_b\tlog2fc\tp_value\tq_value\tdirection\n"
        "Faecalibacterium\tControl\tIBD\t0.23\t0.08\t1.5\t0.01\t0.03\tdown\n"
        "Escherichia\tControl\tIBD\t0.05\t0.21\t-2.0\t0.02\t0.04\tup\n"
        "Bacteroides\tControl\tIBD\t0.29\t0.24\t0.3\t0.4\t0.5\tns\n",
        encoding="utf-8",
    )
    (fig / "pcoa.json").write_text(
        json.dumps(
            {
                "title": "PCoA",
                "points": [
                    {"sample": "c1", "PC1": -0.2, "PC2": 0.1, "group": "Control"},
                    {"sample": "c2", "PC1": -0.15, "PC2": -0.05, "group": "Control"},
                    {"sample": "i1", "PC1": 0.2, "PC2": 0.05, "group": "IBD"},
                    {"sample": "i2", "PC1": 0.25, "PC2": -0.1, "group": "IBD"},
                ],
                "variance_explained": [0.45, 0.22],
            }
        ),
        encoding="utf-8",
    )
    return {
        "outdir": str(tmp_path),
        "run_id": "viz1",
        "user_query": "IBD interactive viz",
        "samples": [
            {"sample_id": "c1", "group": "Control"},
            {"sample_id": "c2", "group": "Control"},
            {"sample_id": "i1", "group": "IBD"},
            {"sample_id": "i2", "group": "IBD"},
        ],
        "artifacts": {
            "statistics": {
                "genus_matrix": str(div / "genus_matrix.tsv"),
                "alpha_diversity": str(div / "alpha_diversity.tsv"),
                "beta_diversity": str(div / "beta_diversity.tsv"),
                "biomarkers": str(bio / "biomarkers.tsv"),
                "groups": {"c1": "Control", "c2": "Control", "i1": "IBD", "i2": "IBD"},
                "biomarker_list": [
                    {
                        "genus": "Faecalibacterium",
                        "log2fc": 1.5,
                        "p_value": 0.01,
                        "q_value": 0.03,
                        "direction": "down",
                    },
                    {
                        "genus": "Escherichia",
                        "log2fc": -2.0,
                        "p_value": 0.02,
                        "q_value": 0.04,
                        "direction": "up",
                    },
                ],
            }
        },
        "config": {"visualization": {"default_q": 0.05}},
    }


def test_build_figures_have_expected_keys(tmp_path: Path):
    state = _demo_state(tmp_path)
    payload = build_interactive_figures(state, default_q=0.05)
    figs = payload["figures"]
    for key in ("composition", "alpha_box", "beta_box", "pcoa", "heatmap", "volcano"):
        assert key in figs
        assert "data" in figs[key]
        assert figs[key]["data"], f"{key} should have traces"
    # heatmap at q=0.05 should prefer significant taxa
    heat = payload["heatmap_by_q"]["0.05"]
    assert "Faecalibacterium" in heat["genera"]
    assert "Escherichia" in heat["genera"]
    assert heat["n_sig"] >= 2


def test_write_dashboard_html(tmp_path: Path):
    state = _demo_state(tmp_path)
    paths = write_interactive_dashboard(state, default_q=0.05)
    dash = Path(paths["dashboard_root"])
    assert dash.exists()
    html = dash.read_text(encoding="utf-8")
    assert "Interactive Metagenomic Analytics" in html
    assert "plot-heatmap" in html
    assert "qSlider" in html
    assert (tmp_path / "report" / "figures" / "composition.plotly.json").exists()
    assert (tmp_path / "report" / "figures" / "pcoa.plotly.json").exists()
