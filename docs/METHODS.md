# Methods note（v0.8）

## Multi-agent system

Orchestration uses specialized agents: **Router** (intent/domain), **Tool Specialist** (command/params from a domain tool KB), **Plan Validator** (completeness + ask-don’t-guess constraints), execution swarm, **Workflow Agent** (RAG over nf-core/Snakemake snippets with error reflection), and **XAI** (leave-one-feature importance for biomarker drivers).

Pipeline:

`parse → router → supervisor → tool_specialist → plan_validator → export_dag → workflow_agent → contract → HITL → swarm → validate → quality → self-heal* → critic → literature → pi_review* → visualization → xai → report`

## Domain constraints

Missing host genome version/index, coordinate system, or differential sample groups trigger validator questions rather than silent defaults (safety-first).

## Bioinformatics & statistics

Unchanged core methods from v0.7 (Shannon, Bray–Curtis, MWU+BH-FDR, optional LEfSe-like/CLR–MWU, classical MDS PCoA). Tool routing additionally consults a curated domain KB (prokaryote vs virus vs MAG vs AMR).

## Limitations

- CAMITAX/TAMA/ViWrap/PhaBOX may be **routing-registered** without local binaries; mock mode records intended commands.
- XAI is a transparent abundance-separation attribution, not full TreeSHAP/LIME on a trained classifier.
- Workflow RAG uses curated nf-core-style snippets, not a live crawl of nf-co.re.
