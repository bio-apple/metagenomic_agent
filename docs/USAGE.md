> 中文版: [USAGE.zh-CN.md](USAGE.zh-CN.md)

# Usage Guide (v0.24)

See [ARCHITECTURE.md](ARCHITECTURE.md) for architecture and design; see [DEPLOY_LINUX.md](DEPLOY_LINUX.md) for Linux deployments with ≥256 GB RAM.

## CLI

Entry point: `meta-agent`.

### `run`

| Option | Default | Description |
|--------|---------|-------------|
| `-i / --input` | required | FASTQ file or directory |
| `-o / --outdir` | `./results` | Output directory |
| `-m / --mode` | `mock` | `mock` \| `local` \| `conda` \| `docker` \| `apptainer` |
| `-q / --query` | generic analysis phrase | Drives Router intent and domain |
| `--metadata` | none | TSV/CSV with `sample_id,group` (recommended for differential analysis) |
| `-c / --config` | `config/default.yaml` | YAML overrides |
| `-y / --yes` | false | Auto-confirm HITL (including Plan Validator prompts) |

```bash
# Demo (recommended: one-click grouped data; or bash scripts/reproduce_demo.sh)
meta-agent run -i examples/demo_data/fastq --metadata examples/demo_data/metadata.tsv \
  -o ./results/demo --mode mock --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"

# Minimal single-sample fixture (CI)
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut microbiome biomarker discovery"

# Real data
meta-agent run -i /data/fastq -o /data/out --mode docker \
  -c config/default.yaml --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

### `serve` / `version`

```bash
meta-agent serve --host 127.0.0.1 --port 8000
meta-agent version
```

Async HITL (Web/API):

```bash
# Start analysis and pause at gates
curl -X POST http://127.0.0.1:8000/analyze -H 'Content-Type: application/json' \
  -d '{"input_path":"tests/fixtures/fastq","outdir":"./results/async1","mode":"mock","hitl_mode":"async"}'

# List pending confirmation gates
curl "http://127.0.0.1:8000/runs/<run_id>/hitl?outdir=./results/async1"

# Submit decisions and resume
curl -X POST http://127.0.0.1:8000/runs/<run_id>/hitl/decide \
  -H 'Content-Type: application/json' \
  -d '{"outdir":"./results/async1","decisions":[{"id":"confirm_report_publish","key":"B"}],"resume":true}'
```

Web UI (analysis + Chat):

```bash
meta-agent serve --host 127.0.0.1 --port 8000
open http://127.0.0.1:8000/ui
```

Chat (grounded Q&A; optionally bind a completed run's outdir / project Memory):

```bash
curl -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -d '{"question":"Why is Faecalibacterium reduced in IBD?","outdir":"./results"}'
```

Container orchestration layer:

```bash
# Orchestration layer (image does not include database/; mount reference DBs as needed)
docker compose up --build
# Production mount of host DBs: META_REF=/ref/databases docker compose up --build
```

Differential-analysis R export (DESeq2 / MaAsLin2 / ANCOM-BC): after a run, see `biomarkers/r_export/`; optionally set `statistics.try_run_r: true`.

Environment variables: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` (optional).

## Configuration (`config/default.yaml`)

| Section | Role |
|---------|------|
| `execution.engine` | `langgraph` (default) \| `nextflow` \| `snakemake`; the latter two consume Agent-written params |
| `execution.skip_swarm_on_engine_ok` | Skip dual-run swarm when NF/SMK succeeds |
| `sandbox.*` / `apptainer.sif_dir` | Container backend; HPC SIF cache directory |
| `docker.*` / `linux.*` | BioContainers overrides, threads/memory/GPU, `scheduler` |
| `cache.per_sample_assembly` | Reuse assembly products under `outdir/<sample>/assembly/` |
| `cache.include_config_hash` | Invalidate step cache when config changes |
| `routing.*` | gLM / dual-path / ε-greedy |
| `paths.*` | Databases, host index, gLM weights/commands |
| `pipeline.*` | Assembly and taxonomy tool lists |
| `validation.*` | QC thresholds; contract / Plan Validator hard-fail |
| `interpretation.*` | Anti-hallucination: `require_grounding`, `require_evidence_chain` |
| `summary.*` | Summary-driven context: `enabled`, `max_llm_chars` |
| `reproducibility.*` | `auto_export`, `seed` |
| `visualization.*` | `default_q`, `lite` (on-demand load), `max_inline_biomarkers` |
| `cache.enabled` | LangGraph step cache |
| `rag.*` | `keyword` \| `semantic`; `authority_dbs` |
| `literature.*` | PubMed / Europe PMC / OpenAlex, etc. |
| `statistics.*` | `demo_mode`, `lefse_like`, `ancom_like` |
| `hitl.auto_confirm` | CI/`--yes` may set `true`; interactive production should use `false` |
| `hitl.mode` | `sync` (CLI Prompt) \| `async` (API pause-on-disk) |
| `hitl.require_assembly_confirm` | Human confirm before Assembly submit |
| `hitl.require_otu_filter_confirm` | Human confirm of rare OTU/ASV thresholds |
| `hitl.require_database_confirm` | Confirm when non-mock and reference DB paths are missing |
| `hitl.require_report_publish_confirm` | Report shareable / draft / hold |
| `hitl.require_self_heal_confirm` | Confirm high-risk self-heal (mock / loosen_qc / lower confidence / downgrade assembler) |
| `hitl.default_self_heal` | `B`=safe only (recommended) · `A`=all · `C`=reject |
| `hitl.default_report_publish` | `A` shareable · `B` draft · `C` hold |
| `statistics.min_prevalence` / `min_rel_abundance` | Feature-filter thresholds after HITL confirmation |
| `project.*` | Host / coordinate system / domain Memory fields |
| `report.manuscript_template` | Manuscript template name |
| `pi.max_replans` | PI replan count |

Reference DB **build steps and directory contract**: [database/README.md](../database/README.md) (step-by-step for Kraken2 / MetaPhlAn / GTDB / CARD); helper script `scripts/build_databases.sh`.

## Metadata example

```tsv
sample_id	group
S1	IBD
S2	Control
```

## Primary outputs

| Path | Description |
|------|-------------|
| `final_report.html` | Full report (embedded multi-panel Plotly figures) |
| `bio_reasoning.md` · `.json` · `_audit.json` | Pre-planning biological reasoning + CoT citation audit |
| `resource_estimate.json` | Estimated runtime/memory/disk and resume hints |
| `cache/steps/` | Swarm intermediate cache (checkpoint resume) |
| `taxonomy_interpretation.md` | Contamination / enrichment hypotheses from taxonomy |
| `functional_interpretation.md` | Functional pathway mechanism notes |
| `interactive_dashboard.html` | Interactive dashboard (q-slider for significant taxa) |
| `quality_report.html` / `quality_status.json` | QC |
| `taxonomy_profile.tsv` | Taxonomy profile |
| `diversity_analysis/` | Alpha/Beta diversity, genus matrix |
| `biomarkers/` | Differential biomarker tables |
| `evidence/claims.md` | Anti-hallucination evidence chain |
| `evidence/evidence_table.md` | Literature evidence table |
| `context/pipeline_summary.json` | Statistical summary for LLM context |
| `planner/planner_plan.md` | Planner: experimental design and full pipeline |
| `executor/submit.{slurm,pbs,sge}` · `job.k8s.yaml` | Executor: multi-scheduler submit specs |
| `executor/cluster_sense.json` · `resource_allocation.json` | Queue pressure and capped CPU/memory/GPU |
| `outdir/<sample>/assembly/checkpoint.json` | MEGAHIT/SPAdes intermediate checkpoint |
| `critic/qc_critic.md` · `bio_qc_chain.json` | QC chain: CheckM2 HQ, unclassified, Q20/Q30 |
| `evidence/grounded_interp.md` | Table-bound interpretation (species/p/q/effect from program tables only) |
| `hitl/critical_gates.json` · `CRITICAL_GATES.md` | Critical HITL audit |
| `hitl/async/session.json` · `state.json` · `AWAITING.md` | Async approval session (API resume) |
| `reasoning/chain.md` · `chain.jsonl` | Cross-agent decision audit |
| `literature_report.md` | Structured literature report |
| `visualization/figure_legends.md` | Figure legends (Figure 1–4) |
| `report/HELD.md` | Placeholder when HITL holds report publication |
| `diversity_analysis/otu_asv_filter.json` | Rare-feature culling summary |
| `reporter/biological_report.md` | Reporter: diversity and pathway interpretation |
| `workflow/params.yaml` · `params.json` | Validated engine params (Schema + task graph) |
| `workflow/ENGINE_README.md` | Nextflow/Snakemake launch notes |
| `workflow/reproducible.nf` · `.smk` · `seeds.json` | Reproducible export |
| `workflow/generated.nf` · `.smk` | Planning-phase RAG drafts |
| `reproducibility/run_manifest.json` | Run manifest + CWL |
| `router_decision.json` | Intent and domain routing |
| `tool_specialist/tool_commands.md` | Tool commands |
| `plan_validation.json` | Plan validation / follow-up questions |
| `xai/feature_importance.md` | Biomarker attribution |
| `report/manuscript/` | Manuscript section drafts |
| `logs/events.jsonl` | Execution events |

## Troubleshooting

| Symptom | Remedy |
|---------|--------|
| Plan Validator asks for host genome | Set `paths.host_index` or `project.host_genome_version`, or use mock/`--yes` |
| No groups → cannot run differential analysis | Provide `--metadata`, or set `statistics.demo_mode: true` |
| HITL stuck | `--yes` / `hitl.auto_confirm: true`; for API use `hitl_mode=async` then `/hitl/decide` |
| Missing host libs / ARM errors | `--mode docker`; self-heal may switch container / pin amd64 |
| OOM / exit 137 | Self-heal raises memory / lowers threads; **assembler downgrade to MEGAHIT only on assembly nodes**; see [SELF_HEAL.md](SELF_HEAL.md) |
| Concern about self-heal “false fixes” | Defaults `hitl.require_self_heal_confirm` + `default_self_heal: B` withhold high-risk actions |
| Viral tools not installed | Specialist still writes commands; install tools or stay in mock |
| Raw stderr flood | Users see self-heal summaries; details in `artifacts.errors` / `logs/` |
