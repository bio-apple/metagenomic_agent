# Methods note for manuscripts (software description)

> 对应实现版本：**v0.6.x**。架构见 [ARCHITECTURE.md](ARCHITECTURE.md)；2026 建议落地见 [PROPOSAL_2026_IMPL.md](PROPOSAL_2026_IMPL.md)。

This document describes what **metagenomic-agent** actually implements today, for Methods / Software sections.

## System

- Orchestration: LangGraph state machine  
  `parse → supervisor → export_dag → contract_check → HITL → swarm → validate → quality_scores → self-heal* → critic → literature → visualization → report`
- Interfaces: CLI (`meta-agent`), FastAPI (`/analyze`), optional Celery/Slurm/Nextflow handoff artifacts
- Decision layer: Skill/Contract registry + playbooks; memory/resource-aware taxonomy tool selection
- Knowledge: curated biological-database RAG (GTDB/NCBI/KEGG/eggNOG/CARD/VFDB/MGnify/BacDive/HMP stubs) + gut microbe KB + Evidence Table (PubMed/Europe PMC when online)

## Bioinformatics modules

| Module | Tools / methods |
|--------|-----------------|
| QC & host | fastp; Bowtie2 or Kneaddata vs HG38 when index configured |
| Taxonomy | Kraken2+Bracken and/or MetaPhlAn; optional gLM microCafe/MicroRAG with long-read routing |
| MAGs | MEGAHIT or metaSPAdes; MetaBAT2/MaxBin2; consensus merge; CheckM2; GTDB-Tk |
| Function | DIAMOND / labeled profile tables (KEGG/eggNOG/CAZy/CARD/VFDB) |
| Statistics | Shannon; Bray–Curtis; Mann–Whitney U + Benjamini–Hochberg FDR |
| Interpretation | Evidence Table + bio-DB RAG + context-aware biological validator |
| Visualization | Taxonomy heatmap data, PCoA stub, co-occurrence stub, exported tables |
| Manuscript | Template sections: Introduction / Methods / Results / Discussion / Limitations / References |

## Self-healing

Structured exit classification (e.g. 137/OOM) triggers parameter reduction and assembler downgrade. Contract post-condition failures can feed critic warnings.

## Reproducibility

Each run writes `report/methods.md`, `report/reproduce.sh`, `reproducibility/` (CWL + run_manifest), and `workflow/dag.json`.

## Limitations to disclose

- Default differential abundance is **not** ANCOM-BC/MaAsLin2/LEfSe.
- Bio-DB RAG ships a compact curated index until full database dumps are configured.
- Manuscript drafts require expert editing; visualization includes stubs for ordination/network until full matrices are enabled.
- Mock mode is for CI/demo only.
