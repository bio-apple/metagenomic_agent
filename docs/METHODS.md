# Methods note（v0.12）

English note suitable for manuscript Methods. Operations: [USAGE.md](USAGE.md). Architecture: [ARCHITECTURE.md](ARCHITECTURE.md).

## Orchestration

Analyses are run by specialized agents under LangGraph rather than a single free-form prompt:

Router → Tool Specialist → Plan Validator → execution swarm (QC, taxonomy, optional assembly/function, statistics) → Critic / Literature → optional PI replan → Visualization / XAI → Report.

Missing host-genome version, coordinate system, or sample groups are escalated (ask, not invent).

## Compute environment

Bioinformatics tools are invoked through a typed sandbox preferring Docker/Apptainer biocontainers (CPU/memory limits; optional `linux/amd64` on Apple Silicon). Failures are classified (OOM, missing binary, architecture/library errors); a self-heal loop may retry with adjusted resources or containers and returns a user-facing summary.

## Analytical methods

| Step | Method |
|------|--------|
| QC / host | fastp; Bowtie2/Kneaddata when configured |
| Taxonomy | Kraken2/MetaPhlAn; optional gLM; virus tools when routed |
| MAGs (optional) | MEGAHIT/metaSPAdes → MetaBAT2 → CheckM2 |
| Statistics | Shannon; Bray–Curtis; MWU + BH-FDR; optional LEfSe-like / CLR–MWU |
| Ordination | Classical MDS (PCoA); Spearman co-occurrence |
| Interpretation | Authority-bound RAG + evidence chains (abundance, p/q, DB IDs, PMIDs) |
| Visualization | Interactive Plotly: composition, alpha/beta boxplots, PCoA, heatmap, volcano (FDR *q* filter) |
| Provenance | Metadata-only LLM context; seeded `reproducible.nf`/`.smk` + `run_manifest.json` |

## Hallucination mitigation

Taxa must resolve in curated GTDB/NCBI indices before biological claims. Allowed claims attach measured abundance and/or differential statistics plus database and literature identifiers. LLM narrative may only paraphrase retrieved authority context.

## Reproducibility artifacts

`workflow/reproducible.nf`, `workflow/reproducible.smk`, `workflow/seeds.json`, `workflow/config_snapshot.yaml`, `reproducibility/run_manifest.json`, `meta_agent.cwl`.

## Limitations

1. Default differential tests are lightweight; LEfSe-like/ANCOM-like are Python approximations, not official packages.  
2. Some routed tools may be registered without local installation.  
3. XAI is abundance-separation attribution, not TreeSHAP on a fitted classifier.  
4. Bio/workflow RAG use curated corpora until full dumps are mounted; mock mode is for software testing only.  
5. Exported workflows wrap `meta-agent run` with executed-DAG provenance; native process graphs need local tools/DBs.
