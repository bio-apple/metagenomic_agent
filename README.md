# Metagenomic Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://img.shields.io/badge/tests-passing-0B6E4F.svg)](tests/)
[![Version](https://img.shields.io/badge/version-0.25.1-0B6E4F.svg)](CHANGELOG.md)
[![Cite](https://img.shields.io/badge/citation-CITATION.cff-0B6E4F.svg)](CITATION.cff)

**Vision.** Turn shotgun metagenomics from a brittle, expert-only tool chain into a **trustworthy scientific agent**: given a research question and sequencing reads, the system plans the analysis, runs community tools in sandboxes, asks for human confirmation when biology or cost is at stake, grounds every claim in program-generated tables, and delivers an audited, publication-ready report.

**Core value.** Workflow managers reproduce *how* tools execute. Metagenomic Agent also decides *what* to run, *when* an analyst must intervene, *how* failures may be repaired without inventing biology, and *how* taxa, *p*/*q*-values, and effect sizes stay bound to evidence — so results are reproducible for reviewers and interpretable for biologists.

Repository: [github.com/bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent) · Manuscript draft: [docs/manuscript/application_note.md](docs/manuscript/application_note.md)

## Graphical abstract

![Overview: Input → Plan+HITL → Execute Swarm with Self-Heal → Interpret → Report](docs/figures/overview.png)

<p align="center"><em>Figure 1.</em> From FASTQ and a research query to an audited report. High-risk repairs and heavy compute steps are human-gated. Vector: <a href="docs/figures/overview.svg"><code>overview.svg</code></a>.</p>

## Capabilities

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
| Citation metadata | [CITATION.cff](CITATION.cff) |
| **Manuscript draft (full text)** | [docs/manuscript/application_note.md](docs/manuscript/application_note.md) |
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
| [docs/manuscript/application_note.md](docs/manuscript/application_note.md) | Application Note manuscript (complete draft) |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## Citation

Please cite this software using [CITATION.cff](CITATION.cff) (GitHub “Cite this repository”).

For the full Application Note draft (Background / Implementation / Results / Availability), see:

**https://github.com/bio-apple/metagenomic_agent/blob/main/docs/manuscript/application_note.md**

A journal DOI will be added to `CITATION.cff` upon publication.

## License

[MIT](LICENSE) — © 2026 bio-apple contributors. Third-party tools and databases retain their own licenses.
