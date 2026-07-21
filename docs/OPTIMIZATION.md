# 设计文档功能闭环（v0.23）

对照 `docs/DESIGN.md` / `Metagenomic_AI_Scientist_Agent_设计文档.docx`。

| 设计章节 | 状态 | 实现 |
|----------|------|------|
| Planner / QC / Taxonomy / Function / Literature / Report | **Done** | 既有多智能体 + 增强 |
| Resistance / Virulence Agent | **Done** | `resistance_agent` · CARD/RGI/DeepARG/ResFinder/AMRFinder/VFDB |
| Evidence Integration Agent | **Done** | `evidence_agent` + Microbiome KG |
| Scientific Reviewer Agent | **Done** | `reviewer_agent`（confidence/concerns） |
| ReAct + Reflection | **Done** | `reflection_agent` |
| Knowledge Graph | **Done** | `knowledge/microbiome_kg.py` |
| Code Agent | **Done** | `code_agent`（sandbox Python） |
| Workflow Engine | **Done** | Nextflow/Snakemake/Docker/Apptainer |
| MetaAgentScore + Benchmarks | **Done** | Planning / Error / Reasoning + `evaluation/meta_agent_score` |
| HITL | **Done** | sync/async 门控 |
| Multi-omics 扩展 | Partial | 路线图占位（转录组/代谢组未全量） |

主链：

```text
Planner → Swarm(QC/Tax/Func/Resistance/Stats) → Critic → Literature
  → Evidence → Reviewer → Reflection → Viz → Code → Report
```
