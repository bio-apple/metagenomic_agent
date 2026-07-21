# Methods note（v0.13）

English note for manuscript Methods. See [USAGE.md](USAGE.md), [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md).

## Orchestration

Analyses use a **Biological Reasoning Layer** before workflow planning: the agent infers study goal (e.g. disease association), recommended assay (typically shotgun metagenomics), pipeline steps (host removal → taxonomy → function → differential tests → interpretation), assembler preference by complexity, and suggested follow-up experiments. A Supervisor (project-manager) agent then decomposes tasks for specialized QC, taxonomy, assembly, function, and statistics agents under LangGraph.

Missing metadata is escalated via structured human-in-the-loop choices (continue / re-QC / skip / abort) rather than invented.

## Compute, analytics, provenance

Sandbox tool calls (Docker/Apptainer), self-heal on classified failures, authority-bound RAG evidence chains, metadata-only LLM context, interactive Plotly dashboards, and seeded Nextflow/Snakemake exports are as in prior versions.

## Limitations

See ROADMAP (FastQC/MultiQC, CAMI suites, vector project memory still partial). Mock mode is for software testing only.
