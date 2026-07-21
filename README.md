# Metagenomic Research Agent

面向科学问题的自主宏基因组分析 Agent。架构与 Linux 生产优化见：

- [`docs/Metagenomic_Research_Agent_Developer_Documentation.md`](docs/Metagenomic_Research_Agent_Developer_Documentation.md)
- [`docs/Metagenomics_Agent_Architecture_and_Optimization.md`](docs/Metagenomics_Agent_Architecture_and_Optimization.md)

## 架构要点（已实现）

```
Coordinator (Supervisor + Memory + Env)
        │
 Execution Engine (LangGraph / Snakemake / Nextflow config)
        │
 QC+Host → Taxonomy → Assembly&MAGs → Stats
        │
 Validator + Self-Heal (OOM→降线程 / metaSPAdes→MEGAHIT)
        │
 Critic → Literature(RAG) → Report
```

### 执行模式

| mode | 说明 |
|------|------|
| `mock` | 无外部依赖演示（默认） |
| `local` | 本机 PATH 工具 |
| `conda` | `conda run -n <env>` 隔离（Linux 生产推荐） |
| `docker` | 公开 biocontainers |

### Linux 生产能力

- `LinuxBioToolRunner`：Bioconda 隔离 + Exit 137/OOM 分类
- `/dev/shm` 数据库预载：`deployment/scripts/preload_shm_db.sh`
- Nextflow 配置自动生成：`results/nextflow/agent.nf.config`
- Slurm sbatch 生成：`deployment.slurm.write_analysis_sbatch`
- Celery 异步任务：`deployment/celery_app.py`（可选依赖）
- Gut Microbe KB RAG：`knowledge/gut_microbe_kb.json`

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "分析肠道宏基因组，做 MAG 与 IBD biomarker"
```

启用分箱（mock 仍可跑）：在 query 含「组装/MAG/分箱」或设置 `pipeline.enable_assembly: true`。

## 测试

```bash
pytest -q
```
