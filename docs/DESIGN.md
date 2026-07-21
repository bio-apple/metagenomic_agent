# Metagenomic AI Scientist Agent — 开发者设计文档

> 源文件：`docs/Metagenomic_AI_Scientist_Agent_设计文档.docx`

Metagenomic AI Scientist Agent 开发者设计文档

    
    项目目标

    构建一个达到 Bioinformatics / Briefings in Bioinformatics / Nature Methods 级别发表潜力的宏基因组生物信息分析智能体（Metagenomic AI Scientist）。

    项目目标不是构建一个简单的：

    LLM + 生信工具调用

    而是构建一个：

    能够理解科研问题、自动规划分析方案、调用生物信息工具、解释结果、发现潜在生物学规律，并进行自我评价和修正的自主科研智能体。

    

    
    
    
    1. 当前项目定位升级

    
    从 Pipeline Wrapper 到 Scientific Agent

    传统模式：

    用户问题    |    vLLM    |    +-- fastp    +-- Kraken2    +-- MetaPhlAn    +-- HUMAnN    |    v分析报告

    该模式属于：

    自动化工具调用

    Pipeline orchestration

    不足：

    缺少科研推理

    缺少分析规划

    缺少错误检测

    缺少生物学解释能力

    

    升级目标：

                        User Question                          |                          v              Scientific Planning Agent                          | ------------------------------------------------- |             |              |                  |QC Agent   Taxonomy Agent   Function Agent   Literature Agent                          |                          v              Evidence Integration Agent                          |                          v              Scientific Reviewer Agent                          |                          v                  Final Report

    

    
    
    
    2. 核心 Agent 架构

    
    2.1 Planner Agent

    职责：

    负责理解科研问题并生成分析计划。

    输入：

    比较疾病组和健康组肠道微生物差异

    输出：

    analysis_plan:  - quality_control  - taxonomic profiling  - alpha diversity  - beta diversity  - differential abundance  - functional profiling  - literature interpretation

    

    功能要求：

    自动拆解科研任务

    选择合适分析流程

    判断数据需求

    生成执行计划

    

    
    
    
    2.2 Data QC Agent

    职责：

    评估测序数据质量。

    工具：

    fastp

    FastQC

    MultiQC

    BBTools

    能力：

    自动判断：

    测序深度是否足够

    是否存在污染

    是否需要过滤

    是否存在批次问题

    输出：

    { "quality_score":0.85, "issues":[    "Low sequencing depth" ], "recommendation": "Increase sequencing depth"}

    

    
    
    2.3 Taxonomy Agent

    职责：

    微生物分类分析。

    支持：

    Kraken2

    Bracken

    MetaPhlAn4

    Centrifuge

    GTDB-Tk

    功能：

    species identification

    abundance estimation

    diversity analysis

    

    
    
    2.4 Functional Analysis Agent

    职责：

    功能注释。

    支持：

    HUMAnN

    KEGG

    MetaCyc

    eggNOG

    输出：

    Species change      |Functional pathway change      |Disease association

    

    
    
    2.5 Resistance / Virulence Agent

    新增高级模块。

    分析：

    
    Antibiotic Resistance

    工具：

    CARD

    ResFinder

    AMRFinderPlus

    
    
    Virulence

    工具：

    VFDB

    输出：

    Detected ARG:blaCTX-MPotential implication:Beta-lactam resistance

    

    
    
    
    2.6 Literature Agent

    职责：

    连接生物学知识。

    数据来源：

    PubMed

    KEGG

    UniProt

    MetaCyc

    功能：

    自动回答：

    为什么某个菌增加？为什么某个pathway下降？是否已有文献支持？

    

    
    
    2.7 Reviewer Agent

    核心创新模块。

    职责：

    类似科研审稿人。

    检查：

    
    数据层面

    sequencing depth

    contamination

    batch effect

    
    
    分析层面

    method suitability

    statistical validity

    
    
    生物学层面

    interpretation accuracy

    输出：

    review: confidence: 0.82 concerns:   - insufficient samples   - possible batch effect recommendation:   perform additional validation

    

    
    
    
    3. Agent 推理框架

    
    推荐采用

    
    
    ReAct + Reflection

    流程：

    Question |Reason |Plan |Execute Tool |Observe Result |Evaluate |Correct |Final Answer

    

    
    
    
    4. Knowledge Graph 增强

    
    建立 Microbiome Knowledge Graph

    结构：

    Microbe |Gene |Protein |Pathway |Disease |Publication

    数据来源：

    GTDB

    KEGG

    UniProt

    CARD

    VFDB

    PubMed

    用途：

    提升：

    生物学解释

    可追溯性

    降低幻觉

    

    
    
    
    5. Multi-omics 扩展路线

    未来支持：

    Metagenomics      |Metatranscriptomics      |Metabolomics      |Host transcriptome

    目标：

    从：

    What microbes exist?

    升级为：

    What biological mechanisms happen?

    

    
    
    6. 自动代码生成能力

    Agent 不应该只调用固定 pipeline。

    增加：

    
    Code Agent

    流程：

    LLM |Generate Python/R script |Sandbox execution |Result validation |Revision

    支持：

    Python

    R

    Nextflow

    

    
    
    
    7. Workflow Engine

    推荐：

    Nextflow

    Snakemake

    Docker

    Singularity

    输出：

    analysis/├── workflow.nf├── environment.yml├── scripts/├── results/├── report/└── provenance.json

    

    
    
    8. Benchmark 设计

    论文级必须建立 Benchmark。

    
    8.1 Pipeline Planning Benchmark

    测试：

    输入科研需求：

    Compare gut microbiome between IBD and healthy controls

    评价：

    Agent 是否生成：

    QC

    taxonomy

    diversity

    statistics

    pathway

    

    
    
    8.2 Error Diagnosis Benchmark

    模拟：

    contamination

    low depth

    batch effect

    测试：

    Agent 是否发现问题。

    

    
    
    8.3 Biological Reasoning Benchmark

    输入：

    Faecalibacterium decreased

    评价：

    是否能解释：

    ↓ Faecalibacterium↓↓ Butyrate production↓Inflammatory phenotype

    

    
    
    
    9. Agent Evaluation Metrics

    建立：

    
    MetaAgentScore

    指标
说明
Planning Accuracy
分析规划正确性
Tool Selection
工具选择能力
Execution Success
流程执行成功率
Biological Reasoning
生物解释能力
Error Detection
错误识别能力
Reproducibility
结果可重复性

    

    
    
    
    10. Human-in-the-loop

    加入科研人员交互。

    例如：

    Agent:

    Detected possible contamination.Choose:A. Remove samplesB. Continue analysisC. Request expert review

    形成：

    AI Scientist        +Human Scientist

    

    
    
    11. 系统架构

    最终目标架构：

                     User                  |                  v        Metagenomic AI Scientist                  | ------------------------------------------------- Planner Agent QC Agent Taxonomy Agent Functional Agent Resistance Agent Literature Agent Statistics Agent Reviewer Agent Report Agent                  |          Knowledge Graph                  |       Workflow Execution Engine                  |          Reproducible Report

    

    
    
    12. 开发优先级

    
    Phase 1：基础 Agent

    目标：

    LLM tool calling

    Pipeline execution

    自动报告

    时间：

    1-2个月

    

    
    
    Phase 2：Scientific Agent

    增加：

    Planner

    Reviewer

    Reflection

    时间：

    3-6个月

    

    
    
    Phase 3：Knowledge-driven Agent

    增加：

    Microbiome KG

    Literature reasoning

    时间：

    6-12个月

    

    
    
    Phase 4：Publication Version

    增加：

    Benchmark

    Multi-cohort validation

    Biological discovery case

    目标：

    Bioinformatics / BIB / Nature Methods

    

    
    
    
    13. 论文创新点设计

    建议论文贡献：

    
    Contribution 1

    提出首个面向宏基因组分析的自主科研 Agent。

    
    
    Contribution 2

    提出多 Agent 协同分析框架。

    
    
    Contribution 3

    建立 Metagenomic Agent Benchmark。

    
    
    Contribution 4

    证明 Agent 能发现传统 pipeline 难以发现的生物学规律。

    

    
    
    
    14. 最终定位

    不要定位为：

    AI-powered metagenomics pipeline

    应该定位为：

    Autonomous AI Scientist for Microbiome Discovery

    核心目标：

    从自动执行分析流程，升级为能够进行科学推理和发现的宏基因组 AI 科学家。