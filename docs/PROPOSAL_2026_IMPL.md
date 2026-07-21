# 2026 优化建议落地对照（v0.6）

对应「Metagenomic Agent 项目优化建议（2026版）」Top3 + 关键 P1。

## P0

| 建议 | 落地 |
|------|------|
| 生物数据库 RAG | `src/metagenomic_agent/rag/`（gtdb/card/vfdb/kegg/mgnify + curated index） |
| 文献 Evidence Table | `agents/evidence.py` + `literature_agent` → `evidence/evidence_table.md` |
| Workflow DAG 化 | `execution/dag_export.py` → `workflow/dag.json` / `dag.mmd`；图节点 `export_dag` |

## P1

| 建议 | 落地 |
|------|------|
| Agent Memory | `coordinator/memory.py` project profile（host/platform/read_length） |
| Tool Registry 决策 | `skills/decision.py`（低内存→Kraken2，长读长→microcafe） |
| 质量评分 | `evaluation/quality_score.py` → `quality/quality_scores.*` |
| 投稿级手稿骨架 | `report/manuscript.py` → `report/manuscript/` |
| Visualization Agent | `agents/visualization_agent.py` → `report/figures/` · `tables/` |

## 主链路增量

`supervisor → export_dag → … → quality_scores → … → literature → visualization → report`

## 仍属后续（诚实）

- 完整 GTDB/CARD/KEGG/MGnify 本地全量索引与向量检索
- LEfSe / 完整 PCoA 距离矩阵可视化
- 多组学与 PI Multi-Agent 编排
