# Architecture

Metagenomic Agent is a **scientific control plane** for shotgun metagenomics: it plans analyses from a research question, executes community tools in sandboxes, gates biology-altering decisions, grounds claims in tables, and emits reproducible reports.

Companion: [USAGE.md](USAGE.md) · [DEPLOY_LINUX.md](DEPLOY_LINUX.md) · [database/README.md](../database/README.md) · [SELF_HEAL.md](SELF_HEAL.md) · [LITERATURE.md](LITERATURE.md) · [MAG_PROTOCOL.md](MAG_PROTOCOL.md) · graphical abstract [`figures/overview.svg`](figures/overview.svg).

## Scope

Metagenomics only (shotgun; related 16S / long-read / MAG workflows). No multi-omics expansion. User-facing strings, reports, and documentation are English; non-English query tokens may still match routing aliases.

## Runtime graph

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → planner → export_dag (+HITL) → workflow → contract → HITL
  → execute swarm (QC · Taxonomy · Function · Resistance · Stats · Assembly/MAG)
  → validate → [self_heal ↻] → critic → [scientific_replan ↻] → literature → evidence
  → reviewer → reflection → pi_review → visualization → code → reporter → xai → report
```

| Loop | Role |
|------|------|
| **self_heal** | Resource/platform retries; **high-risk** patches require HITL ([SELF_HEAL.md](SELF_HEAL.md)) |
| **scientific_replan** | Critic/PI findings that imply tool or pipeline redesign → patch DAG → re-execute (capped) |

Async HITL resumes at `execute_swarm`.

## Agents

| Agent | Responsibility |
|-------|----------------|
| Planner | Research question → analysis plan / DAG |
| QC | fastp / MultiQC-style scoring; host depletion |
| Taxonomy | Kraken2 / Bracken / MetaPhlAn / Centrifuge |
| Assembly / MAG | MEGAHIT · metaSPAdes · Flye → MetaBAT2 · MaxBin2 · CONCOCT · VAMB → DAS Tool → CheckM2 · BUSCO → GTDB-Tk |
| Function | DIAMOND / HUMAnN / pathway summaries |
| Resistance | CARD/RGI · DeepARG · ResFinder · VFDB |
| Statistics | Diversity · differential · UniFrac · PERMANOVA · associations · batch diagnostics · R export |
| Literature / Evidence | PubMed + RAG + microbiome KG; table-bound claims |
| Reviewer / Reflection | Peer-review style checks; observe→correct |
| Reporter | HTML report, Methods, manuscript helpers |

## Evidence and anti-hallucination

- Hybrid RAG + curated microbiome knowledge graph  
- `require_evidence_chain`: species / *p* / *q* / effect from program tables  
- Reasoning audit under `outdir/reasoning/`  
- LLMs receive metadata and retrieved text — not raw reads  

## Human-in-the-loop

| Gate | Typical choices |
|------|-----------------|
| Assembly compute | Submit · lighter assembler · Skip |
| Rare features | Prevalence presets |
| Reference databases | Ready · Partial · Abort |
| High-risk self-heal | Approve all · **Safe only (default)** · Reject |
| Report release | Shareable · Draft · Hold |

## Deployment

- Engines: LangGraph (default); optional Nextflow / Snakemake export via `workflow/params.yaml`  
- Containers: Docker / Apptainer (BioContainers pins in `tools/context.py`)  
- HPC: SLURM / PBS / SGE ([DEPLOY_LINUX.md](DEPLOY_LINUX.md))  
- API / UI: FastAPI `meta-agent serve` → `/ui`  

## Evaluation

| Item | Use |
|------|-----|
| `pytest` | Unit / integration regression |
| Self-heal FPR suite | Curated mis-correction scenarios ([SELF_HEAL.md](SELF_HEAL.md)) |
| MetaAgentScore | Planning / execution / reasoning diagnostics |
| CAMI-style toy | Genus P/R/F1 smoke (not a full OPAMI claim) |

`--mode mock` is for CI and software demos only and must not be reported as biological results.
