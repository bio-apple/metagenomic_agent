# 能力对照（v0.20）

状态：`Done` / `Partial` / `Planned`。

## Human-in-the-Loop

| 项 | 状态 | 说明 |
|----|------|------|
| Assembly 算力确认 | **Done** | `confirm_assembly` |
| OTU/ASV 阈值确认 | **Done** | 四档 prevalence/abundance |
| 审计轨迹 | **Done** | `hitl/critical_gates.json` |
| Web/API 异步审批 | **Done** | `hitl.mode=async` + `/runs/{id}/hitl` |
| 数据库 / 报告外发门控 | **Done** | `confirm_databases`、`confirm_report_publish` |

## 平台能力

| 项 | 状态 |
|----|------|
| Planner / Executor / QC-Critic / Reporter | **Done** |
| BioContainers + Apptainer；SLURM/PBS/SGE | **Done** |
| CheckM2 HQ + unclassified QC；表绑定抗幻觉 | **Done** |
| Schema 化 `params.yaml` + 自愈改参 | **Done** |
| 全量 CAMI 基准 | Partial |
| 向量化项目 Memory | Partial |

用法见 [USAGE.md](USAGE.md)，架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。
