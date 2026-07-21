# 开发者路线图（对照建议）

对照开发者建议与当前 **v0.16**。状态：`Done` / `Partial` / `Planned`。

## 目标架构

```
User → Planner (SOP + manuals) → Executor (params / HPC / K8s)
     → QC & Critic → Reporter (diversity + pathways) → Report
```

| 建议 | 状态 | 现状 |
|------|------|------|
| 工具 Manual / 参数库 RAG | **Done** | `tool_manuals.json`：Kraken2 / GTDB-Tk / Bakta / CheckM2（+ FastQC/Trimmomatic） |
| 16S vs Shotgun SOP | **Done** | `sop_best_practices.json` → `assay_16s_vs_shotgun` |
| 土壤/肠道/海洋预处理 SOP | **Done** | `env_soil_prep` / `env_gut_host_filter` / `env_ocean_prep` |
| Planner Agent | **Done** | `planner_agent` 聚合实验设计与 Pipeline |
| Executor / Bioinfo Agent | **Done** | `executor_agent`：params + Slurm/K8s 提交规格 + swarm |
| QC & Critic Agent | **Done** | Q20/Q30、宿主污染、CheckM 完整度/污染门控 |
| Reporter Agent | **Done** | Alpha/Beta + KEGG/COG/GO 叙述 → `reporter/` |
| 配置驱动 nf/smk | **Done** | v0.15 `params.yaml` |
| 工具 Pydantic Schema | **Done** | 含 gtdbtk / bakta |
| Bakta 原生执行封装 | Partial | Schema + KB + 路由；runner Planned |
| 16S DADA2/QIIME2 执行链 | Partial | SOP/推理已备；执行仍 Planned |
| 向量 Memory | Planned | ContextMemory 文件 |

## 生产提示

```bash
# Planner / Executor 产物
open results/planner/planner_plan.md
cat results/executor/SUBMIT.md
sbatch results/executor/submit.slurm   # HPC
# kubectl apply -f results/executor/job.k8s.yaml  # 需挂载数据卷
```

最终目标：**Autonomous Multi-Agent System for End-to-End Metagenomic Discovery**。
