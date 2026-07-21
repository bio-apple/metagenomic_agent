# Methods note for manuscripts（v0.12）

用法见 [USAGE.md](USAGE.md)，架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## Multi-agent orchestration

Analysis is coordinated by specialized agents rather than a single monolithic prompt. Visualization produces an interactive Plotly dashboard (composition, alpha/beta boxplots, PCoA, heatmap, volcano) with FDR *q*-value filtering of significant taxa, in addition to static figure JSON for archival.

Pipeline graph:

`parse → router → supervisor → tool_specialist → plan_validator → export_dag → workflow_agent → contract → HITL → swarm → validate → quality → self-heal* → critic → literature → pi_review* → visualization → xai → report`

## Summary-driven context

Intermediate Fastq/Bam/Fasta files remain on disk. Agents and LLM prompts consume only statistical metadata via `context/pipeline_summary.json`.

## Reproducibility

After analysis the agent writes `workflow/reproducible.nf`, `workflow/reproducible.smk`, `workflow/seeds.json`, `workflow/config_snapshot.yaml`, and `reproducibility/run_manifest.json`.

## Interactive analytics

Interactive views are written to `interactive_dashboard.html` and `report/figures/*.plotly.json`. Users can zoom, toggle legends, and slide FDR *q* to refresh the heatmap and volcano highlighting. The final HTML report embeds the same figure specs.

## Limitations to disclose

1. Default differential tests are lightweight; LEfSe-like/ANCOM-like are Python approximations.  
2. Some routed tools may be registered without local installation.  
3. XAI is abundance-separation attribution, not TreeSHAP.  
4. Bio RAG uses curated stubs until full dumps are mounted; mock mode is for CI/demos.  
5. Exported `.nf`/`.smk` wrap `meta-agent run` with executed-DAG provenance comments.
