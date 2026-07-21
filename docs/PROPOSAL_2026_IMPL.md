# 2026 + IF10 需求落地对照（v0.7）

本版目标：关闭建议书中此前标注为「后续」的开发项（在无多 GB 全库前提下用算法 + curated + 可插拔 API/钩子完成）。

## 已全部落地（代码存在且有测试）

| 需求 | 路径 / 行为 |
|------|-------------|
| 生物库 RAG + wrapper | `rag/`：gtdb/card/vfdb/kegg/mgnify/bacdive/hmp/refseq/ncbi/eggnog |
| TF-IDF 语义检索 | `rag/embeddings.py`，`retrieve(..., mode="semantic")` |
| Evidence Table 多源 | PubMed / Europe PMC / OpenAlex / Semantic Scholar（config 可开） |
| 显式 DAG | `workflow/dag.json` + 分阶段 Snakemake/Nextflow 文档化 |
| 真实 PCoA | `stats/ordination.py` → `report/figures/pcoa.json` |
| 共现网络 | Spearman → `cooccurrence.json` |
| LEfSe-like / ANCOM-like | `stats/lefse_like.py`, `compositional.py` → biomarkers/ |
| Volcano / Sankey / NMDS 视图 | `visualization_agent.py` |
| 质量评分 | `evaluation/quality_score.py` |
| 手稿分节 | `report/manuscript/` |
| Project Memory | `context/context.json` |
| Tool 决策 | `skills/decision.py` |
| 契约硬失败 | `validation.contract_hard_fail` |
| gLM 外部推理钩子 | `paths.glm_inference_cmd` + `glm_weights` |
| PI Agent | `agents/pi_agent.py` → 可选 replan |
| Benchmark | `evaluation/benchmarks.py` + `tests/test_v07_complete.py` |

## 仍需外部环境（非缺功能，缺数据/GPU）

- 挂载完整 GTDB/CARD/KEGG 转储替换 curated 索引
- 配置真实 gLM 权重与 `glm_inference_cmd`
- 正式期刊统计包（ANCOM-BC R / MaAsLin2）——本仓库提供导出表 + 近似方法

## 主链路

`… → literature → pi_review → visualization → report`
