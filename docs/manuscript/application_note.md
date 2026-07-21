# Metagenomic Agent: a multi-agent platform for reproducible shotgun metagenomic analysis

**Manuscript type:** Application Note / Software article (draft for journal submission)  
**Software version described:** 0.24.0  
**Figure:** [`docs/figures/overview.svg`](../figures/overview.svg) (Graphical abstract / Overview)

> **Editorial note.** This draft follows common *Application Note* / BMC *Software* conventions. For *Bioinformatics* (OUP), replace the unstructured Background–Results–Conclusions abstract with the journal’s four-part abstract (*Summary*; *Availability and Implementation*; *Contact*; *Supplementary information*) and keep total length ≤ ~4 printed pages (~2,000–2,600 words + one figure). Author names, affiliations, and funding should be completed before submission.

---

## Title

**Metagenomic Agent: multi-agent planning, sandboxed execution, and evidence-grounded reporting for shotgun metagenomics**

*(The software name “Metagenomic Agent” is included in the title as required for Application Notes.)*

---

## Authors

bio-apple contributors<sup>1</sup>  
<sup>1</sup> Project maintainers — see repository contributors list.

**Corresponding author:** GitHub Issues at https://github.com/bio-apple/metagenomic_agent/issues  
*(Replace with institutional email before submission.)*

---

## Abstract

**Background:** Shotgun metagenomic studies increasingly rely on long tool chains (quality control, taxonomic profiling, functional annotation, assembly, differential abundance, and literature synthesis). Existing workflow managers excel at reproducible execution but leave research planning, failure recovery, evidence grounding, and human oversight largely to analysts. Large language model (LLM)–based agents can draft analyses, yet unconstrained tool use risks non-reproducible commands and biologically misleading “self-corrections.”

**Results:** We present **Metagenomic Agent** (`meta-agent`), an open-source multi-agent system that maps a natural-language research question and FASTQ inputs to a validated analysis directed acyclic graph (DAG), executes bioinformatics tools in container sandboxes, and produces an audited HTML report with Methods, figures, and biomarker tables. The platform integrates human-in-the-loop (HITL) gates for compute-heavy and biology-altering decisions; a self-heal loop that retries with resource or platform patches while withholding high-risk corrections pending analyst approval; and evidence constraints so reported taxa and effect sizes must derive from program-generated tables. A public one-click demo and unit/integration tests (130+ passing at v0.23.1) support reviewer reproduction without reference databases. A curated self-heal false-positive suite reports trigger and post-policy action false-positive rates of 0.0 on nine mis-correction scenarios.

**Conclusions:** Metagenomic Agent provides a citable, MIT-licensed path from research question to reproducible metagenomic report, with explicit availability, safety controls for automated repair, and documentation suitable for journal review. The software is publicly available without email request.

**Keywords:** metagenomics; multi-agent systems; reproducibility; human-in-the-loop; workflow automation; evidence grounding

---

## 1. Introduction

Culture-independent shotgun sequencing remains central to microbiome discovery, yet end-to-end analysis still demands expert orchestration of heterogeneous tools (e.g. fastp, Kraken2/Bracken, MetaPhlAn, DIAMOND, MEGAHIT/metaSPAdes, CheckM2, GTDB-Tk) and careful statistical and literature interpretation (Quince *et al.*, 2017; Beghini *et al.*, 2021). Workflow engines such as Nextflow and Snakemake improve computational reproducibility (Di Tommaso *et al.*, 2017; Mölder *et al.*, 2021) but do not, by themselves, (i) translate a scientific question into an analysis plan, (ii) decide when analyst confirmation is mandatory, or (iii) prevent language-model assistants from inventing statistics or silently relaxing quality thresholds after a failure.

Metagenomic Agent addresses this gap as an **Application Note–oriented software contribution**: a LangGraph-orchestrated multi-agent platform whose primary deliverable is not a new aligner, but a trustworthy research loop—plan, execute, validate, heal under policy, ground claims, review, and report—scoped strictly to metagenomics (no multi-omics expansion).

---

## 2. Implementation

### 2.1 Architecture

The runtime graph proceeds as (Figure 1 / graphical abstract):

1. **Input** — FASTQ files or directories, optional phenotype metadata (`sample_id`, `group`), and a free-text research query.  
2. **Plan + HITL** — routing and biological reasoning agents propose goals; a planner emits a DAG; critical gates confirm assembly compute, reference-database readiness, OTU/ASV prevalence filters, high-risk self-heal actions, and report publishability. Validated parameters are written to `workflow/params.yaml` for LangGraph and optional Nextflow/Snakemake handoff.  
3. **Execute (swarm)** — specialist agents invoke QC, taxonomy, function, antimicrobial resistance/virulence, statistics, and optional MAG assembly tools via Docker/Apptainer (BioContainers) or local/conda backends.  
4. **Validate / Self-Heal** — technical and biological checks; classified errors map to structured patches (memory, threads, container platform). High-risk actions (`switch_to_mock_fallback`, `loosen_qc`, `lower_kraken_confidence`, `downgrade_assembler`) are withheld by default pending HITL.  
5. **Interpret → Output** — critic, literature, evidence integration (hybrid RAG + microbiome knowledge graph), scientific reviewer, reflection, visualization, code sandbox, and XAI summaries feed `final_report.html`, Methods text, biomarker exports (including optional DESeq2/MaAsLin2/ANCOM-BC R scripts), and MetaAgentScore diagnostics.

LLMs operate on metadata and retrieved context; raw sequencing reads are not prompted into the model context.

### 2.2 Interfaces

- **CLI:** `meta-agent run`, `meta-agent serve`, `meta-agent version`  
- **HTTP API / Web UI:** FastAPI service with asynchronous HITL endpoints and a browser UI (`/ui`)  
- **Configuration:** YAML (`config/default.yaml`), environment variables for OpenAI-compatible APIs (optional for mock demos)

### 2.3 Reliability controls for automated repair

Self-heal proposals are risk-tiered. A scenario catalog (`evaluation/self_heal_fpr`) scores false triggers and forbidden actions; under the default safe policy, forbidden actions are not applied without explicit approval. Details are documented in `docs/SELF_HEAL.md` for transparent Methods reporting.

---

## 3. Results

### 3.1 Reviewer-facing reproducibility

Clone the public repository and run:

```bash
bash scripts/reproduce_demo.sh
```

This installs the package (if needed), executes the automated test suite, and runs an end-to-end **mock** analysis on bundled paired FASTQ (`examples/demo_data/`) with case/control metadata, producing `final_report.html` without reference databases or GPU. Mock mode is intended for software and orchestration verification and must not be interpreted as biological truth; production runs use `docker` or `apptainer` modes after building databases as described in `database/README.md`.

### 3.2 Self-heal false-positive evaluation

On nine curated mis-correction scenarios (taxonomy OOM incorrectly downgrading assemblers; soft QC wording falsely triggering threshold relaxation; silent mock fallback; etc.), the suite reports:

| Metric | Value (v0.23.1) |
|--------|-----------------|
| Trigger false-positive rate | 0.0 |
| Action false-positive rate (forbidden proposed) | 0.0 |
| Action false-positive rate after safe HITL policy | 0.0 |

These figures characterize the regression catalog, not an epidemiological estimate over all real cluster logs; expanding the catalog is ongoing work.

### 3.3 Example use

Given IBD versus control gut shotgun reads and a biomarker-oriented query, Metagenomic Agent plans taxonomy and differential analysis, requests metadata-aware statistics, applies HITL-confirmed prevalence filters when enabled, and emits grounded claims tied to biomarker tables plus a literature/evidence section. Assembly remains optional and confirmable before heavy compute.

---

## 4. Discussion

Metagenomic Agent complements—not replaces—Nextflow/Snakemake by owning the scientific control plane: intent, safety gates, and evidence discipline. Limitations include dependence on external reference databases for non-mock runs; optional LLM quality for narrative sections; and self-heal metrics derived from synthetic scenarios. We deliberately exclude multi-omics scope to keep validation and documentation focused.

---

## 5. Availability and Requirements

| Item | Details |
|------|---------|
| **Project name** | Metagenomic Agent (`metagenomic-agent` / CLI `meta-agent`) |
| **Project home page** | https://github.com/bio-apple/metagenomic_agent |
| **Operating system(s)** | Linux (recommended for production); macOS supported for development and mock demos; Windows via WSL2 |
| **Programming language** | Python ≥ 3.10 |
| **Other requirements** | For mock/demo: pip-installable dependencies only. For production tool execution: Docker and/or Apptainer/Singularity; reference databases (Kraken2, MetaPhlAn, GTDB-Tk, host Bowtie2 index, etc.) as documented in `database/README.md`; optional OpenAI-compatible API key for LLM-enhanced reasoning; optional Nextflow or Snakemake for engine handoff; ≥256 GB RAM recommended for large-memory production configs (`docs/DEPLOY_LINUX.md`) |
| **License** | MIT License |
| **Any restrictions to use by non-academics** | None under MIT (commercial use permitted subject to license terms). Third-party bioinformatics tools and reference databases retain their own licenses and citation requirements. Optional cloud LLM APIs are subject to the provider’s terms and may incur cost. |

**Availability statement (data and software):** Source code, MIT license text, citation metadata (`CITATION.cff`), unit/integration tests, bundled demo FASTQ, and the one-click reproduce script are publicly available at the project home page. **No materials are available solely upon email request.**

---

## 6. Availability of data and materials

All software and demo datasets analysed for the reproducibility claim in this note are included in the GitHub repository https://github.com/bio-apple/metagenomic_agent (paths: `examples/demo_data/`, `tests/fixtures/fastq/`, `scripts/reproduce_demo.sh`). Self-heal evaluation definitions are in `src/metagenomic_agent/evaluation/self_heal_fpr.py`.

---

## 7. Competing interests

The authors declare that they have no competing interests. *(Update if applicable.)*

---

## 8. Funding

*(Insert funding agencies and grant numbers, or state “None.”)*

---

## 9. Authors’ contributions

Software design, implementation, documentation, and manuscript draft: bio-apple contributors. *(Expand with CRediT roles before submission.)*

---

## 10. Acknowledgements

We thank the open-source bioinformatics and container communities (including BioContainers) whose tools Metagenomic Agent orchestrates.

---

## 11. References

1. Beghini F, *et al.* (2021) Integrating taxonomic, functional, and strain-level profiling of diverse microbial communities with bioBakery 3. *eLife* 10:e65088.  
2. Di Tommaso P, *et al.* (2017) Nextflow enables reproducible computational workflows. *Nat Biotechnol* 35:316–319.  
3. Mölder F, *et al.* (2021) Sustainable data analysis with Snakemake. *F1000Research* 10:33.  
4. Quince C, *et al.* (2017) Shotgun metagenomics, from sampling to analysis. *Nat Biotechnol* 35:833–844.  
5. Wood DE, Lu J, Langmead B (2019) Improved metagenomic analysis with Kraken 2. *Genome Biol* 20:257.  
6. Parks DH, *et al.* (2022) GTDB: an ongoing census of bacterial and archaeal diversity through a phylogenetically consistent, rank normalized and complete genome-based taxonomy. *Nucleic Acids Res* 50:D785–D794.

*(Expand with MetaPhlAn, CARD, LangGraph, and journal-specific citation style on submission.)*

---

## Figure legend

**Figure 1. Graphical abstract of Metagenomic Agent.** End-to-end flow from FASTQ and research query through planning with human-in-the-loop gates, container-sandboxed specialist execution with a policy-constrained self-heal loop, evidence-grounded interpretation, and audited report outputs. Vector figure: `docs/figures/overview.svg`.

---

## Appendix A — *Bioinformatics* (OUP) abstract alternative

If submitting as an Application Note to *Bioinformatics*, use:

**Summary:** Metagenomic Agent is an open-source multi-agent platform that plans, executes, and evidence-grounds shotgun metagenomic analyses with HITL safety gates and policy-constrained self-healing, producing reproducible audited reports from FASTQ and a research query.

**Availability and Implementation:** Freely available under the MIT license at https://github.com/bio-apple/metagenomic_agent; implemented in Python 3.10+; runs on Linux and macOS (Windows via WSL2); production execution via Docker/Apptainer.

**Contact:** https://github.com/bio-apple/metagenomic_agent/issues  

**Supplementary information:** Documentation under `docs/`; graphical abstract `docs/figures/overview.svg`; self-heal reliability note `docs/SELF_HEAL.md`.

---

## Appendix B — Word-count guidance

Main text (§1–4) of this draft is intentionally concise for Application Note limits. Before submission: finalize authors/funding, run spell-check, export Figure 1 as high-resolution PNG/PDF if the journal disallows SVG, and verify the GitHub URL resolves publicly.
