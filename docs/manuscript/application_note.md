# Metagenomic Agent: multi-agent planning, sandboxed execution, and evidence-grounded reporting for shotgun metagenomics

**Manuscript type:** Application Note / Software  
**Software version:** 0.26.0  
**Figure:** [`docs/figures/overview.svg`](../figures/overview.svg)

---

## Authors

bio-apple contributors<sup>1</sup>  
<sup>1</sup> See the GitHub contributors list.

**Correspondence:** https://github.com/bio-apple/metagenomic_agent/issues  
*(Replace with institutional email before journal submission.)*

---

## Abstract

**Background:** Shotgun metagenomic studies require long tool chains—quality control, taxonomic profiling, functional annotation, optional assembly and MAG recovery, differential abundance, and literature synthesis. Workflow managers improve computational reproducibility but leave research planning, failure recovery under biological constraints, evidence grounding, and analyst oversight largely manual. Unconstrained language-model assistants risk non-reproducible commands and misleading “self-corrections.”

**Results:** We present **Metagenomic Agent** (`meta-agent`), an open-source multi-agent system that maps a natural-language research question and FASTQ inputs to a validated analysis directed acyclic graph (DAG), executes bioinformatics tools in container sandboxes, and produces an audited HTML report with Methods, figures, and biomarker tables. Human-in-the-loop (HITL) gates cover compute-heavy and biology-altering decisions. A self-heal loop retries resource or platform failures while withholding high-risk corrections pending approval. Reported taxa and effect sizes are constrained to program-generated tables, supported by hybrid retrieval and a curated microbiome knowledge graph. A public one-click demo and automated test suite support software reproduction without reference databases. On a curated self-heal false-positive catalog (nine mis-correction scenarios), trigger and post-policy action false-positive rates are 0.0.

**Conclusions:** Metagenomic Agent provides a citable MIT-licensed path from research question to reproducible metagenomic report, with explicit availability, safety controls for automated repair, and documentation suitable for journal review. All software and demo materials are public; none are available solely upon request.

**Keywords:** metagenomics; multi-agent systems; reproducibility; human-in-the-loop; evidence grounding; workflow automation

---

## 1. Introduction

Culture-independent shotgun sequencing remains central to microbiome discovery, yet end-to-end analysis still demands expert orchestration of heterogeneous tools (e.g. fastp, Kraken2/Bracken, MetaPhlAn, DIAMOND, MEGAHIT/metaSPAdes, CheckM2, GTDB-Tk) and careful statistical and literature interpretation (Quince *et al.*, 2017; Beghini *et al.*, 2021). Workflow engines such as Nextflow and Snakemake improve computational reproducibility (Di Tommaso *et al.*, 2017; Mölder *et al.*, 2021) but do not, by themselves, translate a scientific question into an analysis plan, decide when analyst confirmation is mandatory, or prevent assistants from inventing statistics or silently relaxing quality thresholds after failure.

Metagenomic Agent addresses this gap as a software contribution: a LangGraph-orchestrated multi-agent platform whose primary deliverable is a trustworthy research loop—plan, execute, validate, heal under policy, ground claims, review, and report—scoped strictly to metagenomics.

---

## 2. Implementation

### 2.1 Architecture

The runtime (Figure 1) proceeds as:

1. **Input** — FASTQ, optional phenotype metadata (`sample_id`, `group`, covariates), and a free-text research query.  
2. **Plan + HITL** — routing and biological reasoning propose goals; a planner emits a DAG; gates confirm assembly compute, database readiness, feature-filter presets, high-risk self-heal actions, and report publishability. Parameters are written to `workflow/params.yaml` for LangGraph and optional Nextflow/Snakemake handoff.  
3. **Execute** — specialist agents invoke QC, taxonomy, function, AMR/virulence, statistics, and optional MAG recovery via Docker/Apptainer (BioContainers) or local/conda backends.  
4. **Validate / Self-Heal / Replan** — technical and biological checks; resource patches may auto-apply; high-risk actions are withheld by default. Critic findings that imply pipeline redesign trigger a capped scientific replan.  
5. **Interpret → Output** — literature and evidence integration, reviewer/reflection, visualization, and reporting produce `final_report.html`, Methods text, biomarkers (including optional DESeq2 / MaAsLin3 / ANCOM-BC2 / ALDEx2 R scripts), and evaluation diagnostics.

Raw sequencing reads are not prompted into language-model context.

### 2.2 Interfaces

- **CLI:** `meta-agent run`, `meta-agent serve`, `meta-agent version`  
- **HTTP API / Web UI:** FastAPI with asynchronous HITL and browser UI (`/ui`)  
- **Configuration:** YAML (`config/`), optional OpenAI-compatible API keys for LLM-enhanced narrative paths  

### 2.3 Reliability controls

Self-heal proposals are risk-tiered. A scenario catalog (`evaluation/self_heal_fpr`) scores false triggers and forbidden actions; under the default safe policy, forbidden actions are not applied without approval ([docs/SELF_HEAL.md](../SELF_HEAL.md)).

---

## 3. Results

### 3.1 Software reproducibility

```bash
bash scripts/reproduce_demo.sh
```

This runs the test suite and an end-to-end **mock** analysis on bundled FASTQ (`examples/demo_data/`), producing `final_report.html` without reference databases. Mock mode verifies software orchestration and must not be interpreted as biological truth. Production runs use `docker` or `apptainer` after building databases ([database/README.md](../../database/README.md)).

### 3.2 Self-heal false-positive evaluation

On nine curated mis-correction scenarios:

| Metric | Value |
|--------|-------|
| Trigger false-positive rate | 0.0 |
| Action false-positive rate (forbidden proposed) | 0.0 |
| Action false-positive rate after safe HITL policy | 0.0 |

These figures characterize the regression catalog, not an epidemiological estimate over all cluster logs.

### 3.3 Intended use

Given case–control gut shotgun reads and a biomarker-oriented query, the agent plans taxonomy and differential analysis, applies HITL-confirmed prevalence filters when enabled, and emits grounded claims tied to biomarker tables with literature/evidence sections. MAG recovery remains optional and confirmable before heavy compute.

---

## 4. Discussion

Metagenomic Agent complements Nextflow/Snakemake by owning the scientific control plane: intent, safety gates, and evidence discipline. Limitations include dependence on external reference databases for non-mock runs; optional LLM quality for narrative sections; synthetic self-heal scenarios; and phylogenetic UniFrac / production DAS Tool–BUSCO paths that require installed binaries and reference trees. Multi-omics is deliberately out of scope.

---

## 5. Availability and Requirements

| Item | Details |
|------|---------|
| **Project name** | Metagenomic Agent (`metagenomic-agent` / CLI `meta-agent`) |
| **Project home page** | https://github.com/bio-apple/metagenomic_agent |
| **Operating system(s)** | Linux (production); macOS (development / software demos); Windows via WSL2 |
| **Programming language** | Python ≥ 3.10 |
| **Other requirements** | Demo: pip dependencies only. Production: Docker and/or Apptainer; reference databases (Kraken2, MetaPhlAn, GTDB-Tk, host index, …); optional OpenAI-compatible API; ≥256 GB RAM recommended for large-memory configs |
| **License** | MIT |
| **Restrictions for non-academics** | None under MIT. Third-party tools/databases retain their licenses. Optional cloud LLM APIs may incur cost. |

**Availability statement:** Source code, license, `CITATION.cff`, tests, demo FASTQ, and `scripts/reproduce_demo.sh` are public. **No materials are available solely upon email request.**

---

## 6. Data and materials

Software and demo datasets: https://github.com/bio-apple/metagenomic_agent (`examples/demo_data/`, `tests/fixtures/fastq/`, `scripts/reproduce_demo.sh`). Self-heal definitions: `src/metagenomic_agent/evaluation/self_heal_fpr.py`.

---

## 7. Competing interests

The authors declare that they have no competing interests.

---

## 8. Funding

*(Insert agencies and grant numbers, or “None.”)*

---

## 9. Authors’ contributions

Software design, implementation, documentation, and manuscript draft: bio-apple contributors. *(Expand with CRediT roles before submission.)*

---

## 10. Acknowledgements

We thank the open-source bioinformatics and BioContainers communities whose tools Metagenomic Agent orchestrates.

---

## 11. References

1. Beghini F, *et al.* (2021) Integrating taxonomic, functional, and strain-level profiling of diverse microbial communities with bioBakery 3. *eLife* 10:e65088.  
2. Di Tommaso P, *et al.* (2017) Nextflow enables reproducible computational workflows. *Nat Biotechnol* 35:316–319.  
3. Mölder F, *et al.* (2021) Sustainable data analysis with Snakemake. *F1000Research* 10:33.  
4. Quince C, *et al.* (2017) Shotgun metagenomics, from sampling to analysis. *Nat Biotechnol* 35:833–844.  
5. Wood DE, Lu J, Langmead B (2019) Improved metagenomic analysis with Kraken 2. *Genome Biol* 20:257.  
6. Parks DH, *et al.* (2022) GTDB: an ongoing census of bacterial and archaeal diversity through a phylogenetically consistent taxonomy. *Nucleic Acids Res* 50:D785–D794.

---

## Figure legend

**Figure 1. Graphical abstract.** End-to-end flow from FASTQ and research query through planning with HITL gates, container-sandboxed execution with policy-constrained self-heal, evidence-grounded interpretation, and audited report outputs (`docs/figures/overview.svg`).

---

## Bioinformatics (OUP) abstract alternative

**Summary:** Metagenomic Agent is an open-source multi-agent platform that plans, executes, and evidence-grounds shotgun metagenomic analyses with HITL safety gates and policy-constrained self-healing, producing reproducible audited reports from FASTQ and a research query.

**Availability and Implementation:** MIT license at https://github.com/bio-apple/metagenomic_agent; Python 3.10+; Linux/macOS (Windows via WSL2); production via Docker/Apptainer.

**Contact:** https://github.com/bio-apple/metagenomic_agent/issues  

**Supplementary information:** `docs/`; graphical abstract `docs/figures/overview.svg`; self-heal note `docs/SELF_HEAL.md`.
