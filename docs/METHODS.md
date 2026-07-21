# Methods note for manuscripts（v0.7）

本说明描述 **metagenomic-agent 当前实现**，可直接改写进 Software / Methods 段落。用法见 [USAGE.md](USAGE.md)，架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## System

- Orchestration: LangGraph  
  `parse → supervisor → export_dag → contract_check → HITL → swarm → validate → quality_scores → self-heal* → critic → literature → pi_review* → visualization → report`
- Interfaces: CLI `meta-agent`, FastAPI `/analyze`
- Decision: Skill/Contract/Playbook；读长与内存感知工具选择；可选契约硬失败

## Bioinformatics

| Module | Methods |
|--------|---------|
| QC / host | fastp; Bowtie2 or Kneaddata when configured |
| Taxonomy | Kraken2/Bracken and/or MetaPhlAn; optional gLM (microCafe/MicroRAG) |
| MAGs | MEGAHIT or metaSPAdes → MetaBAT2/MaxBin2 → CheckM2 → GTDB-Tk |
| Function | DIAMOND / labeled profiles (KEGG/eggNOG/CAZy/CARD/VFDB) |
| Statistics | Shannon; Bray–Curtis; Mann–Whitney U + BH-FDR; optional LEfSe-like / CLR–MWU |
| Ordination / networks | Classical MDS (PCoA); Spearman co-occurrence |
| Knowledge | Curated bio-DB RAG (± TF-IDF); Evidence Table (PubMed/Europe PMC/OpenAlex/S2 when online) |
| Reporting | HTML report; manuscript sections; CWL + `reproduce.sh` |

## Reproducibility

Each run writes `report/methods.md`, `report/reproduce.sh`, `reproducibility/`, and `workflow/dag.json`.

## Limitations to disclose

1. Default differential abundance is **not** official ANCOM-BC / MaAsLin2 / LEfSe; LEfSe-like and ANCOM-like are Python approximations. Export tables for journal-grade tools when required.  
2. Bio-DB RAG uses a compact curated index unless full database dumps are mounted.  
3. gLM inference requires user-supplied weights and optional `glm_inference_cmd`.  
4. Mock mode is for software testing only.
