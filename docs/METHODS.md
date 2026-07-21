# Methods note for manuscripts（v0.11）

用法见 [USAGE.md](USAGE.md)，架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## Multi-agent orchestration

Analysis is coordinated by specialized agents rather than a single monolithic prompt:

1. **Router** — classifies intent (taxonomy, MAG, virus, biomarker, …) and scientific domain.  
2. **Tool Specialist** — emits tool-specific commands/parameters from a curated domain knowledge base.  
3. **Plan Validator** — checks DAG completeness and required metadata; **asks instead of guessing** when host genome version, coordinate system, or sample groups are missing.  
4. **Execution swarm** — QC, taxonomy, assembly/function, statistics under LangGraph.  
5. **Workflow Agent** — RAG over nf-core/Snakemake-style snippets; records self-correction notes from runtime errors.  
6. **Literature / Evidence** — authority-bound bio-DB RAG + optional online literature APIs; ungrounded taxa rejected.  
7. **XAI** — leave-one-feature group-separation attribution for biomarker drivers.  
8. **Report** — HTML, manuscript sections, CWL reproducibility bundle, evidence chains, post-run `.nf`/`.smk`.

Pipeline graph:

`parse → router → supervisor → tool_specialist → plan_validator → export_dag → workflow_agent → contract → HITL → swarm → validate → quality → self-heal* → critic → literature → pi_review* → visualization → xai → report`

## Summary-driven context

Intermediate Fastq/Bam/Fasta files remain on disk. Agents and LLM prompts consume only statistical metadata (read counts, Q30, classification rate, contig N50, CheckM completeness/contamination, biomarker p/q-values) via `context/pipeline_summary.json`.

## Reproducibility

After analysis the agent writes `workflow/reproducible.nf`, `workflow/reproducible.smk`, `workflow/seeds.json`, `workflow/config_snapshot.yaml`, and `reproducibility/run_manifest.json` for peer review and independent re-execution.

## Tooling & environment

Tools are invoked through a typed sandbox (`ToolCallRequest`) preferring **Docker/Apptainer** biocontainers with CPU/memory limits and optional `linux/amd64` platform (important on Apple Silicon). Failures are classified from stderr (OOM, missing binary, architecture mismatch, shared-library errors); the self-heal loop adjusts resources/tools/container settings and reports a **user-facing summary** instead of raw logs. Snakemake/Nextflow remain available as optional external engines.

| Module | Methods |
|--------|---------|
| QC / host | fastp; Bowtie2/Kneaddata when configured |
| Taxonomy | Kraken2/MetaPhlAn; optional gLM; domain routing may prefer virus tools (ViWrap/PhaBOX) when relevant |
| MAGs | MEGAHIT/metaSPAdes → MetaBAT2 → CheckM2 |
| Statistics | Shannon; Bray–Curtis; MWU + BH-FDR; optional LEfSe-like / CLR–MWU |
| Ordination | Classical MDS (PCoA); Spearman co-occurrence |
| Interpretation | Evidence Table + evidence chains; XAI |
| Provenance | Pipeline summary + seeded Nextflow/Snakemake export |

## Hallucination mitigation

Biological claims are allowed only when the taxon resolves in the curated **GTDB / NCBI Taxonomy** index and carry measured abundance and/or differential-test statistics plus database identifiers and literature IDs when available. LLM narrative may only paraphrase retrieved authority context.

## Limitations to disclose

1. Default differential tests are lightweight; LEfSe-like/ANCOM-like are Python approximations, not official packages.  
2. Some routed tools (CAMITAX, TAMA, ViWrap, PhaBOX) may be registered without local installation.  
3. XAI is transparent abundance-separation attribution, not TreeSHAP on a fitted classifier.  
4. Workflow/bio RAG use curated corpora (stubs until full dumps are mounted); mock mode is for software testing only.  
5. Exported `.nf`/`.smk` wrap `meta-agent run` with the executed DAG recorded as provenance comments; full native process graphs depend on mounted tools/DBs.
