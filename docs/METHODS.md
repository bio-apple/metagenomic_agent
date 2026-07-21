# Methods note（v0.14）

See [USAGE.md](USAGE.md), [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md).

## Orchestration

A Biological Reasoning Layer matches scenario CoT examples and **must cite** external community sources (nf-core, BioStars, workflow RAG) before workflow planning. Tool Specialist attaches registered skill I/O contracts; execution is not free-form LLM shell. LangGraph swarm persists step caches for resume; optional Nextflow `-resume` / Snakemake `--rerun-incomplete` when `execution.engine` is set.

## Production analytics

Pre-run resource estimates report wall-clock, peak memory, and disk. Interactive dashboards default to **lite** mode (summary + on-demand Plotly JSON) to avoid browser collapse on large cohorts.

## Limitations

Mock mode is for CI. Full CAMI benchmarks and vector project memory remain partial (ROADMAP).
