# Metagenomic Research Agent

Autonomous AI agent system for end-to-end metagenomic analysis and biological discovery.

See the full design in [`docs/Metagenomic_Research_Agent_Developer_Documentation.md`](docs/Metagenomic_Research_Agent_Developer_Documentation.md).

## Architecture

```
User (natural language)
        │
 Supervisor Agent
        │
 ┌──────┼──────────┬──────────┐
 QC   Taxonomy  Assembly  Function
        │
 Statistics Agent
        │
 Critic Agent
        │
 Literature Agent
        │
 Report Generator
```

Implemented with **LangGraph** + optional **Snakemake** (`workflow/Snakefile`) + **FastAPI** (`meta-agent serve`).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # optional LLM keys (DeepSeek/Qwen/OpenAI)

meta-agent run \
  --input tests/fixtures/fastq \
  --outdir ./results \
  --mode mock \
  --query "Analyze shotgun metagenomic samples from IBD patients and healthy controls. Identify microbial biomarkers." \
  --yes
```

Outputs (documentation §8):

```
results/
├── quality_report.html
├── taxonomy_profile.tsv
├── functional_profile.tsv
├── diversity_analysis/
├── biomarkers/
├── literature_summary/
└── final_report.html
```

## API

```bash
meta-agent serve --host 127.0.0.1 --port 8000
# POST /analyze  GET /health
```

## Docker mode

Requires image `meta:latest` (or configure `docker.image`) and databases under `database/` / `config/default.yaml` paths.

## Agents & tools

| Agent | Module | Tools |
|-------|--------|-------|
| Supervisor | `agents/supervisor.py` | LLM / heuristic planner |
| QC | `agents/qc_agent.py` | fastp, host filter |
| Taxonomy | `agents/taxonomy_agent.py` | Kraken2, Bracken, MetaPhlAn |
| Assembly | `agents/assembly_agent.py` | MEGAHIT, MetaBAT2, GTDB-Tk |
| Function | `agents/function_agent.py` | KEGG/eggNOG/CAZy/CARD/VFDB |
| Statistics | `agents/statistics_agent.py` | Shannon, Bray-Curtis, biomarkers |
| Critic | `agents/critic_agent.py` | reliability checks |
| Literature | `agents/literature_agent.py` | PubMed + mechanism KB |
| Report | `report/generator.py` | HTML / methods / reproduce.sh |

## Tests

```bash
pytest -q
```
