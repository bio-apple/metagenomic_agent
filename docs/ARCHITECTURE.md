> 中文版: [ARCHITECTURE.zh-CN.md](ARCHITECTURE.zh-CN.md)

# Architecture and Design (v0.23)

Positioning: **Autonomous AI Scientist for Microbiome Discovery** (a metagenomics research agent, not a thin pipeline wrapper).

Companion docs: [USAGE.md](USAGE.md) (usage) · [DEPLOY_LINUX.md](DEPLOY_LINUX.md) (≥256 GB deployment) · [database/README.md](../database/README.md) (reference databases) · [SELF_HEAL.md](SELF_HEAL.md) (self-heal FPR / HITL).

## Goals

Understand the research question → plan analysis → invoke bioinformatics tools → interpret results → ground in literature/KG → self-evaluate and correct → produce a reproducible report.

**Scope**: metagenomics (shotgun / 16S-related workflows). No multi-omics expansion.

**Project language**: documentation, CLI/Web UI, HITL prompts, and reports are **English**. Optional Chinese tokens remain only as query-matching aliases in routers/knowledge triggers so non-English research questions still route correctly.

## Orchestration backbone

Graphical abstract (repository README): [`docs/figures/overview.svg`](figures/overview.svg).

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → planner → export_dag(+HITL) → workflow → contract → HITL
  → executor swarm (QC · Taxonomy · Function · Resistance · Stats · Assembly…)
  → validate → [self_heal ↻ swarm] → critic → literature → evidence → reviewer → reflection
  → pi_review → viz → code_agent → reporter → xai → report(+MetaAgentScore)
```

`self_heal`: classify error → propose actions → **high-risk requires HITL** → update params/DAG → re-run swarm (`max_retries`, default 2). Details: [SELF_HEAL.md](SELF_HEAL.md).

Async HITL: `resume_pipeline` continues from `execute_swarm`.

## Agent overview

| Agent | Responsibility | Path |
|-------|----------------|------|
| Planner | Research question → analysis plan | `agents/planner_agent.py` |
| QC | fastp / MultiQC-style scoring | `agents/qc_agent.py` |
| Taxonomy | Kraken2 / Bracken / MetaPhlAn / Centrifuge | `agents/taxonomy_agent.py` |
| Function | DIAMOND / KEGG / HUMAnN | `agents/function_agent.py` |
| Resistance | CARD/RGI / DeepARG / ResFinder / VFDB | `agents/resistance_agent.py` |
| Statistics | Alpha/Beta / differential / R export | `agents/statistics_agent.py` |
| Literature | PubMed + RAG | `agents/literature_agent.py` |
| Evidence | Statistics + literature + KG | `agents/evidence_agent.py` |
| Reviewer | Peer-review-style confidence/concerns | `agents/reviewer_agent.py` |
| Reflection | ReAct Observe→Correct | `agents/reflection_agent.py` |
| Code | Sandboxed Python table analysis | `agents/code_agent.py` |
| Reporter / Report | Interpretation and HTML/manuscript | `agents/reporter_agent.py`, `report/` |
| Executor | HPC / containers / swarm | `agents/executor_agent.py` |

## Knowledge and anti-hallucination

- Hybrid RAG (`rag.mode=hybrid`) + Microbiome KG (`knowledge/microbiome_kg.py`)
- Full reference DB build: see [database/README.md](../database/README.md) (Kraken2 / MetaPhlAn / GTDB / CARD…)
- Table binding: `require_evidence_chain` (species/p/q/effect from program tables)
- Reasoning audit: `outdir/reasoning/chain.md`
- Project Memory: `ContextMemory.retrieve` (TF-IDF)

## Human-in-the-Loop

| Gate | Options |
|------|---------|
| Assembly compute | Submit · MEGAHIT · Skip |
| Rare OTU/ASV | Balanced / Strict / Lenient / None |
| Reference DB paths | Ready · Partial · Abort |
| **Self-Heal high-risk** | Approve all · **Safe only (default)** · Reject heal |
| Report release | Shareable · Draft · Hold |

`hitl.mode`: `sync` (CLI) \| `async` (API `/runs/{id}/hitl`).

## Workflow and deployment

- Engines: LangGraph (default) · Nextflow · Snakemake; params in `workflow/params.yaml`
- Containers: Docker / Apptainer (BioContainers); orchestration via `Dockerfile` / `docker-compose.yml`
- HPC: SLURM / PBS / SGE; large-memory config in [DEPLOY_LINUX.md](DEPLOY_LINUX.md)
- UI: `GET /ui` · Chat: `POST /chat`

## Evaluation

| Item | Description |
|------|-------------|
| MetaAgentScore | Planning / Tool / Execution / Reasoning / Error / Repro |
| CAMI toy | Genus-level P/R/F1 (CI regression; not full OPAMI) |
| Functional closure | All agents in the table above are implemented |

## Methods highlights

- Cite community sources before planning (nf-core / BioStars / tool manuals)
- Skill contracts + Pydantic Schema; no free-form shell
- Checkpoint / step cache; `mock` is for CI only
