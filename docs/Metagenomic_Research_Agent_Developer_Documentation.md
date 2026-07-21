# Metagenomic Research Agent

> **归档说明（v0.5）**：本文为早期开发者总览，主链路与模块表可能已过时。  
> 请优先阅读：[ARCHITECTURE.md](ARCHITECTURE.md) · [USAGE.md](USAGE.md) · [METHODS.md](METHODS.md) · 仓库 [README](../README.md)。

## An Autonomous AI Agent System for End-to-End Metagenomic Analysis and Biological Discovery

------------------------------------------------------------------------

## 1. Overview

Metagenomic Research Agent is an intelligent bioinformatics agent
framework designed for automated metagenomic data analysis.

Unlike traditional bioinformatics pipelines that require manually
predefined workflows, this system uses Large Language Models (LLMs) and
multi-agent collaboration to:

-   Understand biological questions expressed in natural language
-   Automatically design analysis workflows
-   Select appropriate bioinformatics tools
-   Execute computational pipelines
-   Evaluate analysis quality
-   Interpret biological significance
-   Generate research reports

The goal is to transform metagenomic analysis from:

    Human-designed pipeline
            |
            |
            v
    Manual execution

into:

    Scientific Question
            |
    AI Research Agent
            |
    Autonomous Analysis
            |
    Biological Discovery

------------------------------------------------------------------------

# 2. System Architecture

                             User
                              |
                    Natural Language Query
                              |
                     Supervisor Agent
                              |
            -------------------------------------
            |          |          |             |
         QC Agent  Taxonomy   Assembly     Function
                  Agent       Agent        Agent
            |          |          |             |
         fastp     MetaPhlAn   MEGAHIT    HUMAnN3
                   Kraken2    MetaBAT2    eggNOG
            -------------------------------------
                              |
                     Statistical Agent
                              |
                     Critic Agent
                              |
                  Literature Agent
                              |
                    Report Generator

------------------------------------------------------------------------

# 3. Design Principles

## 3.1 Autonomous Planning

The system does not execute fixed workflows.

Example:

User:

    Find microbial signatures associated with inflammatory disease.

Agent:

    Plan:

    1. Inspect sequencing quality
    2. Remove host contamination
    3. Profile microbial composition
    4. Compare groups
    5. Identify biomarkers
    6. Search supporting literature
    7. Generate interpretation

------------------------------------------------------------------------

## 3.2 Multi-Agent Collaboration

  Agent              Responsibility
  ------------------ --------------------------------
  Supervisor Agent   Task planning and coordination
  QC Agent           Read quality evaluation
  Taxonomy Agent     Species identification
  Assembly Agent     Genome reconstruction
  Function Agent     Gene/pathway annotation
  Statistics Agent   Differential analysis
  Critic Agent       Quality control
  Literature Agent   Biological interpretation
  Report Agent       Scientific report generation

------------------------------------------------------------------------

# 4. Core Components

## Supervisor Agent

Receives user requests and decomposes them into executable tasks.

Example:

``` json
{
 "tasks":[
  {
   "name":"quality_control",
   "agent":"QC Agent"
  },
  {
   "name":"taxonomy_profile",
   "agent":"Taxonomy Agent"
  }
 ]
}
```

------------------------------------------------------------------------

## QC Agent

Purpose:

Evaluate sequencing quality.

Supported tools:

  Tool      Function
  --------- ----------------
  fastp     Read trimming
  FastQC    Quality report
  MultiQC   Summary report

Output:

``` json
{
 "Q30":95,
 "adapter_removed":true,
 "status":"PASS"
}
```

------------------------------------------------------------------------

## Taxonomy Agent

Purpose:

Microbial community profiling.

Supported tools:

  Tool         Application
  ------------ --------------------------
  Kraken2      Taxonomic classification
  Bracken      Abundance estimation
  MetaPhlAn4   Marker-based profiling

------------------------------------------------------------------------

## Assembly Agent

Purpose:

Recover metagenome assembled genomes (MAGs).

Workflow:

    Raw Reads
     |
    MEGAHIT
     |
    Contigs
     |
    MetaBAT2
     |
    MAGs
     |
    GTDB-Tk

------------------------------------------------------------------------

## Functional Agent

Purpose:

Identify biological functions.

Databases:

  Database   Purpose
  ---------- -----------------------
  KEGG       Pathways
  eggNOG     Protein annotation
  CAZy       Carbohydrate enzymes
  CARD       Antibiotic resistance
  VFDB       Virulence factors

------------------------------------------------------------------------

## Statistics Agent

Functions:

-   Alpha diversity
-   Beta diversity
-   Differential abundance
-   Biomarker discovery

Tools:

    R
    vegan
    DESeq2
    ANCOM-BC
    LEfSe

------------------------------------------------------------------------

## Critic Agent

Evaluates reliability.

Checks:

-   Sequencing depth
-   Classification rate
-   Statistical validity
-   Biological interpretation

Example:

``` json
{
 "warning":"Low microbial classification rate",
 "recommendation":"Try MetaPhlAn4 profiling"
}
```

------------------------------------------------------------------------

## Literature Agent

Connects results with biological knowledge.

Functions:

-   PubMed search
-   Literature retrieval
-   Mechanism explanation

Example:

    Faecalibacterium decreased

    Interpretation:

    Faecalibacterium produces butyrate,
    which may influence intestinal barrier integrity.

------------------------------------------------------------------------

# 5. Software Architecture

    metagenomic-agent/

    ├── agents/
    │   ├── supervisor.py
    │   ├── qc_agent.py
    │   ├── taxonomy_agent.py
    │   ├── assembly_agent.py
    │   ├── function_agent.py
    │   ├── critic_agent.py
    │   └── literature_agent.py

    ├── tools/
    │   ├── fastp.py
    │   ├── kraken.py
    │   ├── metaphlan.py
    │   └── megahit.py

    ├── workflow/
    │   └── Snakefile

    ├── database/
    │   ├── kraken_db
    │   ├── gtdb
    │   └── eggnog

    ├── report/
    │   └── generator.py

    └── api/
        └── server.py

------------------------------------------------------------------------

# 6. Technology Stack

## LLM Layer

Supported:

-   GPT series
-   Claude
-   Qwen
-   DeepSeek

Local deployment:

    Ollama
    +
    Qwen3
    +
    OpenWebUI

## Agent Framework

Recommended:

    LangGraph
    LangChain
    AutoGen
    CrewAI

## Workflow Engine

    Snakemake
    Nextflow

## Containerization

    Docker
    Singularity

------------------------------------------------------------------------

# 7. Example Usage

User:

    Analyze shotgun metagenomic samples from
    IBD patients and healthy controls.
    Identify microbial biomarkers.

Execution:

    Supervisor:
    Create workflow

    QC Agent:
    Run fastp

    Taxonomy Agent:
    Run MetaPhlAn4

    Statistics Agent:
    Run ANCOM-BC

    Literature Agent:
    Search mechanisms

    Report Agent:
    Generate report

------------------------------------------------------------------------

# 8. Output

Generated results:

    results/

    ├── quality_report.html
    ├── taxonomy_profile.tsv
    ├── functional_profile.tsv
    ├── diversity_analysis/
    ├── biomarkers/
    ├── literature_summary/
    └── final_report.html

------------------------------------------------------------------------

# 9. Future Development

## Version 1.0

Basic workflow automation:

-   Tool calling
-   Pipeline execution
-   Report generation

## Version 2.0

Research Agent:

-   Multi-agent collaboration
-   Memory
-   Literature reasoning
-   Quality evaluation

## Version 3.0

Autonomous Discovery Agent:

-   Generate hypotheses
-   Design validation experiments
-   Compare external datasets
-   Recommend follow-up experiments

------------------------------------------------------------------------

# 10. Research Vision

    AI Scientist

            |

    Autonomous Bioinformatics Research System

            |

    New Biological Discovery
