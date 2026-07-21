# 开发者路线图（对照建议）

对照开发者建议与当前 **v0.17**。状态：`Done` / `Partial` / `Planned`。

## HPC / 云原生

| 建议 | 状态 | 现状 |
|------|------|------|
| Docker / Apptainer + BioContainers | **Done** | `DEFAULT_IMAGES` pin；`run_docker` 在 apptainer 模式走 sandbox |
| SLURM / PBS / SGE 提交 | **Done** | `executor/submit.{slurm,pbs,sge}` + 资源封顶 |
| 集群负载感知 | **Done** | `execution/cluster.py`（squeue/qstat/本地 mem） |
| GPU 申请字段 | **Done** | `linux.gpus` + SBATCH `--gres` |
| 中间 Checkpoint（MEGAHIT/SPAdes） | **Done** | `cache.per_sample_assembly` + `checkpoint.json` |
| 步骤缓存 config 失效 | **Done** | `cache.include_config_hash` |
| NF/SMK 与 swarm 互斥 | **Done** | `execution.skip_swarm_on_engine_ok` |
| 实时 GPU 负载 / fairshare | Partial | 字段已备；深度调度 Planned |
| SIF 自动 pull 预热 | Partial | `apptainer.sif_dir` 写入脚本；自动 pull Planned |

## 领域 / 编排（既有）

| 建议 | 状态 |
|------|------|
| Planner / Executor / QC-Critic / Reporter | Done (v0.16) |
| 工具手册 + SOP RAG | Done |
| 配置驱动 nf/smk + Schema | Done (v0.15) |

```bash
# HPC
cat results/executor/SUBMIT.md
sbatch results/executor/submit.slurm   # 或 qsub …pbs / …sge

# 容器
meta-agent run … --mode apptainer   # 或 docker；镜像见 BioContainers pins
```
