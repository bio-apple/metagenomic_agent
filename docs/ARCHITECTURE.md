# 架构说明

面向 **v0.17**。详见 [USAGE.md](USAGE.md)、[ROADMAP.md](ROADMAP.md)。

## 设计

```
User → Planner → params.yaml
     → Executor（集群感知 → 资源封顶 → SLURM/PBS/SGE/K8s）
     → Docker / Apptainer（BioContainers）
     → Swarm + step cache + 组装 Checkpoint
     → QC & Critic → Reporter → Report
```

| 主题 | 路径 |
|------|------|
| BioContainers 镜像 | `tools/context.py` `DEFAULT_IMAGES` |
| Docker↔Apptainer 贯通 | `ToolContext.run_docker` → sandbox |
| 集群感知 / 封顶 | `execution/cluster.py` |
| 提交脚本 | `deployment/slurm.py` → `executor/submit.{slurm,pbs,sge}` |
| 组装 Checkpoint | `execution/checkpoint.py` · `outdir/<sample>/assembly/` |
| 步骤缓存 | `execution/step_cache.py`（含 config hash） |

```
… → planner → export_dag(+resource_estimate+cluster_sense)
  → executor(sense→cap→submit specs→swarm|nf/smk) → …
```
