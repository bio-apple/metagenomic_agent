# Changelog

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
