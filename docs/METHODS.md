# Methods note for manuscripts (software description)

> 对应实现版本：**v0.5.x**。中文使用说明见 [USAGE.md](USAGE.md)；架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

This document describes what **metagenomic-agent** actually implements today, for Methods / Software sections.

## System

- Orchestration: LangGraph state machine  
  `parse → supervisor → contract_check → HITL → swarm → validate → self-heal* → critic → literature → report`
- Interfaces: CLI (`meta-agent`), FastAPI (`/analyze`), optional Celery/Slurm/Nextflow handoff artifacts
- Decision layer: Skill/Contract registry + playbooks; pre/post condition checks before execution and HITL escalation on hard failures

## Bioinformatics modules

| Module | Tools / methods |
|--------|-----------------|
| QC & host | fastp; Bowtie2 or Kneaddata vs HG38 when index configured |
| Taxonomy | Kraken2+Bracken and/or MetaPhlAn; optional gLM microCafe/MicroRAG with long-read routing and dual-path fusion |
| MAGs | MEGAHIT or metaSPAdes; MetaBAT2/MaxBin2; consensus merge; CheckM2; GTDB-Tk |
| Function | DIAMOND / labeled profile tables (KEGG/eggNOG/CAZy/CARD/VFDB) |
| Statistics | Shannon; Bray–Curtis; Mann–Whitney U + Benjamini–Hochberg FDR |
| Interpretation | Gut / IBD biomarker KB + context-aware biological validator; optional PubMed E-utilities |

## Self-healing

Structured exit classification (e.g. 137/OOM) triggers parameter reduction and assembler downgrade (metaSPAdes → MEGAHIT). Contract post-condition failures can feed critic warnings and recovery recommendations.

## Reproducibility

Each run writes:

- `report/methods.md` (executed DAG + versions)
- `report/reproduce.sh` (full CLI)
- `reproducibility/run_manifest.json` + `reproducibility/meta_agent.cwl` (+ Nextflow params when applicable)

Mock mode is for CI/demo only.

## Limitations to disclose

- Default differential abundance is **not** ANCOM-BC/MaAsLin2/LEfSe; export tables and re-analyze for journal-grade stats.
- gLM adapters ship with mock/local stubs until real model weights and runtimes are configured.
- External Nextflow/Snakemake engines are optional; by default compute runs in-process via LangGraph agents.
