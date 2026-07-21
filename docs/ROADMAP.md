# 开发者路线图（对照建议）

对照开发者建议与当前 **v0.18**。状态：`Done` / `Partial` / `Planned`。

## QC 与可解释性

| 建议 | 状态 | 现状 |
|------|------|------|
| CheckM2 Completeness>90% / Contamination<5% | **Done** | `bio_qc` high-quality 门控 + medium 技术硬失败 |
| Kraken2/MetaPhlAn unclassified 过高告警 | **Done** | `max_unclassified_fraction` + 换库/confidence 建议 |
| 解读强制引用真实表格 | **Done** | `grounded_interp`：物种/p/q/log2FC/LDA 表绑定 |
| PCoA / LEfSe 叙事护栏 | **Done** | Reporter/Interpreter 仅表内实体 |
| Per-bin CheckM 全表扫描 | Partial | 样本级 + CheckM TSV 首行；全 bin 分级 Planned |

## HPC / 领域（既有）

| 建议 | 状态 |
|------|------|
| BioContainers + SLURM/PBS/SGE + Checkpoint | Done (v0.17) |
| Planner / Executor / Reporter + SOP RAG | Done (v0.16) |
