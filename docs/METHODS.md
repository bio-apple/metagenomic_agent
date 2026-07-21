# Methods note for manuscripts (software description)

This document describes what **metagenomic-agent** actually implements today (v0.4.x), for Methods / Software sections.

## System

- Orchestration: LangGraph state machine (`parse → supervisor → HITL → swarm → validate → self-heal* → critic → literature → report`)
- Interfaces: CLI (`meta-agent`), FastAPI (`/analyze`), optional Celery/Slurm/Nextflow handoff artifacts

## Bioinformatics modules

| Module | Tools / methods |
|--------|-----------------|
| QC & host | fastp; Bowtie2 or Kneaddata vs HG38 when index configured |
| Taxonomy | Kraken2+Bracken and/or MetaPhlAn |
| MAGs | MEGAHIT or metaSPAdes; MetaBAT2/MaxBin2; consensus merge; CheckM2; GTDB-Tk |
| Function | DIAMOND / labeled profile tables (KEGG/eggNOG/CAZy/CARD/VFDB) |
| Statistics | Shannon; Bray–Curtis; Mann–Whitney U + Benjamini–Hochberg FDR |
| Interpretation | Gut Microbe KB RAG + optional PubMed E-utilities |

## Self-healing

Structured exit classification (e.g. 137/OOM) triggers parameter reduction and assembler downgrade (metaSPAdes → MEGAHIT).

## Reproducibility

Each run writes `report/methods.md` (executed DAG + versions) and `report/reproduce.sh` (full CLI). Mock mode is for CI/demo only.

## Limitations to disclose

- Default differential abundance is **not** ANCOM-BC/MaAsLin2/LEfSe; export tables and re-analyze for journal-grade stats.
- External Nextflow/Snakemake engines are optional; by default compute runs in-process via LangGraph agents.
