# 开发者路线图（对照建议）

对照开发者建议与当前 **v0.19**。状态：`Done` / `Partial` / `Planned`。

## Human-in-the-Loop

| 建议 | 状态 | 现状 |
|------|------|------|
| Assembly 高算力提交前确认 | **Done** | `confirm_assembly` 门控 + 资源预估展示 |
| 极低频 OTU/ASV 阈值确认 | **Done** | 四档 prevalence/abundance 预设 |
| 审计轨迹 | **Done** | `hitl/critical_gates.json` |
| Web/API 异步审批 | Planned | 现为 CLI Rich Prompt |
| 更多门控（数据库下载、外发报告） | Partial | 可扩 `hitl_gates` |

## 既有能力

QC 链 / 表绑定抗幻觉 (v0.18) · HPC 容器与 Checkpoint (v0.17) · Planner/Executor (v0.16)
