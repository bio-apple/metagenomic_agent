# Metagenomic Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://img.shields.io/badge/tests-passing-0B6E4F.svg)](tests/)
[![Version](https://img.shields.io/badge/version-0.25.1-0B6E4F.svg)](CHANGELOG.md)

**An autonomous multi-agent system for reproducible shotgun metagenomic analysis** — research-question planning, container-sandboxed tool execution, evidence-grounded interpretation, and audited reporting.

Repository: [github.com/bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## Graphical abstract

![Overview: Input → Plan+HITL → Execute Swarm with Self-Heal → Interpret → Report](docs/figures/overview.png)

<p align="center"><em>Figure 1.</em> From FASTQ and a research query to an audited report. High-risk repairs and heavy compute steps are human-gated. Vector: <a href="docs/figures/overview.svg"><code>overview.svg</code></a>.</p>

## Why this software

Workflow managers reproduce *how* tools run. Metagenomic Agent also decides *what* to run for a scientific question, when analyst confirmation is mandatory, how failures may be repaired without inventing biology, and how claims are bound to program-generated tables.

| Capability | Summary |
|------------|---------|
| Planning | Natural-language query → validated analysis DAG |
| Execution | BioContainers (Docker/Apptainer), conda, or local backends |
| Safety | HITL gates; high-risk self-heal actions withheld by default |
| Grounding | Taxa / *p* / *q* / effects from result tables; RAG + knowledge graph |
| Reporting | HTML report, Methods text, biomarkers, optional R journal exports |

**Scope:** metagenomics (shotgun, related amplicon/long-read/MAG paths). Not a multi-omics suite.

## Availability

| Resource | Location |
|----------|----------|
| Source | This public repository |
| License | [MIT](LICENSE) |
| Citation | [CITATION.cff](CITATION.cff) |
| Manuscript draft | [docs/manuscript/application_note.md](docs/manuscript/application_note.md) |
| Demo data | [examples/demo_data/](examples/demo_data/) |
| Reproduce | [`bash scripts/reproduce_demo.sh`](scripts/reproduce_demo.sh) |
| Tests | `pytest` (unit + integration) |

Nothing is “available upon request.” The bundled demo uses `--mode mock` for **software** reproducibility; production biology requires reference databases.

## Quick start

### 1. Deploy software

```bash
git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent
docker compose up --build -d          # UI: http://127.0.0.1:8000/ui
# or: python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

Reference databases are **not** in the image. See [database/README.md](database/README.md).

### 2. Download reference databases (production)

```bash
export DB_ROOT=/ref/databases
bash scripts/build_databases.sh --layout
# then Kraken2 / MetaPhlAn / host index / … — see database/README.md
META_REF=/ref/databases docker compose up --build -d
```

### 3. Run

```bash
# Reviewer smoke test (no DBs)
bash scripts/reproduce_demo.sh

# Production
meta-agent run -i /data/fastq -o /data/out --mode docker \
  -c config/site.yaml --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/USAGE.md](docs/USAGE.md) | CLI, API, configuration, outputs |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, agents, HITL, evaluation |
| [docs/SELF_HEAL.md](docs/SELF_HEAL.md) | Self-heal policy and FPR scenario suite |
| [docs/DEPLOY_LINUX.md](docs/DEPLOY_LINUX.md) | Large-memory Linux / HPC deployment |
| [database/README.md](database/README.md) | Reference database build |
| [docs/manuscript/application_note.md](docs/manuscript/application_note.md) | Application Note manuscript |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## Citation

Cite this repository via [CITATION.cff](CITATION.cff). A journal citation will replace the software citation upon publication.

## License

[MIT](LICENSE) — © 2026 bio-apple contributors. Third-party tools and databases retain their own licenses.
