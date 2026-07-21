# Changelog

## 0.23.1

- Self-Heal reliability: node-scoped heuristics, high-risk HITL gate (`confirm_self_heal`), FPR scenario suite (`evaluation/self_heal_fpr`) + [docs/SELF_HEAL.md](docs/SELF_HEAL.md)
- README: journal-style polish + graphical abstract [`docs/figures/overview.svg`](docs/figures/overview.svg)
- Application Note manuscript draft: [`docs/manuscript/application_note.md`](docs/manuscript/application_note.md)

## 0.23.0

- Design-doc agents: Resistance/Virulence, Evidence Integration, Scientific Reviewer, Reflection, Code
- Microbiome Knowledge Graph; Centrifuge + QC MultiQC score; MetaAgentScore + planning/error/reasoning benchmarks
- Graph: literature → evidence → reviewer → reflection → code → report
- Docs: keep USAGE / ARCHITECTURE / DEPLOY_LINUX / database README / CHANGELOG only（无多组学路线图）

## 0.22.0

- CAMI-style toy taxonomy P/R/F1 benchmark (`evaluation/cami_toy`)
- Project Memory TF-IDF retrieve (`ContextMemory.retrieve`) wired into `/chat`
- Copilot Web UI at `GET /` and `/ui`
- Journal R export: DESeq2 / MaAsLin2 / ANCOM-BC scripts under `biomarkers/r_export/`

## 0.21.0

- Unified `reasoning/` decision audit (`chain.jsonl` / `chain.md`)
- Structured `literature_report.md`; hybrid RAG (`rag.mode=hybrid`); knowledge dir contract under `database/`
- Dockerfile + docker-compose for orchestration API; `POST /chat` grounded Copilot
- Figure legends; CONCOCT + CARD/RGI + DeepARG + VirSorter2/CheckV (mock + BioContainers pins)

## 0.20.0

- Async HITL for Web/API: `hitl.mode=async`, session under `hitl/async/`, `resume_pipeline`
- API: `hitl_mode` on `POST /analyze`; `GET/POST /runs/{run_id}/hitl`
- Gates: `confirm_databases` (missing `paths.*`), `confirm_report_publish` (shareable / draft / hold)

## 0.19.0

- Critical HITL gates: confirm before Assembly compute; choose OTU/ASV prevalence cutoffs
- Mid-swarm re-checks; audit under `hitl/`; statistics apply confirmed filters

## 0.18.0

- Automated bio QC chain: CheckM2 high-quality (≥90% / ≤5%) + Kraken2/MetaPhlAn unclassified gates
- Hallucination guardrails: species / p / q / effect sizes must come from biomarkers/LEfSe tables
- `grounded_interp` for Reporter/Interpreter; `require_evidence_chain` enforced in evidence claims

## 0.17.0

- BioContainers pins + `run_docker` routes to Apptainer/Docker sandbox
- Cluster load sense (SLURM/PBS/SGE/local) with CPU/GPU/memory capping before submit
- Scheduler scripts `submit.{slurm,pbs,sge}`; assembly checkpoints + config-hashed step cache
- Skip LangGraph swarm when external Nextflow/Snakemake succeeds

## 0.16.0

- Domain RAG: tool manuals (Kraken2/GTDB-Tk/Bakta/CheckM2) + SOP (16S vs Shotgun; gut/soil/ocean prep)
- Explicit roles: Planner, Executor (Slurm/K8s specs), QC & Critic (Q20/Q30/CheckM), Reporter (diversity/pathways)
- GTDB-Tk / Bakta schemas + tool_domain_kb entries; bio_reasoning cites SOP/manuals

## 0.15.0

- Agent emits validated `workflow/params.yaml|json` for Nextflow/Snakemake (no free-form LLM shell)
- Pydantic schemas for FastQC / Trimmomatic / MEGAHIT / MetaBAT2 / HUMAnN3 / Kraken2 (+ fastp, CheckM2, MetaPhlAn)
- Self-heal loop: error digest → increase memory / fix paths / switch tools → rewrite params → retry

## 0.14.0

- Skill-contract-aware Tool Specialist; LangGraph step cache (`cache/steps`) for resume
- Bio Reasoning CoT library + mandatory nf-core/BioStars citations + audit JSON
- Lite interactive dashboard (on-demand Plotly JSON; summary-first)
- Pre-run resource estimate; Snakemake `--rerun-incomplete` alongside Nextflow `-resume`

## 0.13.0

- Biological Reasoning Layer; taxonomy/functional interpretation; HITL A/B/C

## 0.12.0 – 0.1.x

- Interactive Plotly, summary context, evidence chains, container sandbox, multi-agent MVP
