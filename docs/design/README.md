# Design sources

- [`Metagenomic Agent Development.docx`](Metagenomic%20Agent%20Development.docx) — product roadmap (Planner/Critic/replan, MAG, Statistical Reasoning, literature/KG; sample & assay types).
- [`DEVELOPMENT_ROADMAP.txt`](DEVELOPMENT_ROADMAP.txt) — plain-text extract of the same roadmap.

## Implementation status

| Priority | Status | Version |
|----------|--------|---------|
| P1 Planner / Critic / self-correction (scientific replan) | Done | 0.24+ |
| P2 MAG (Flye/VAMB/DAS Tool/CheckM2/BUSCO/GTDB; cohort auto-MAG) | Done (lite/mock + BioContainers pins) | 0.24–0.25 |
| P3 Statistical Reasoning (diagnostics, UniFrac, PERMANOVA, associations, batch loop) | Done | 0.24–0.25 |
| P4/P5 Literature Evidence + Knowledge Graph | Done (deepened confidence/contradiction/resistance) | 0.25 |

Publication-grade DAS Tool / BUSCO / reference-tree UniFrac / lme4 still require installed binaries and real phylogeny inputs; Python paths are Methods-disclosed fallbacks for CI and orchestration.
