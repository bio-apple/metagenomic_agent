# 架构说明

面向 **v0.15**。详见 [USAGE.md](USAGE.md)、[ROADMAP.md](ROADMAP.md)。

## 设计

```
User → Router → Bio Reasoning
     → Supervisor → Tool Specialist (Pydantic Schema + skill contracts)
     → params.yaml/json → resource estimate → HITL
     → LangGraph swarm 或 Nextflow/Snakemake（-resume / --rerun-incomplete）
     → 失败：日志摘要 → 自愈改参 → 重写 params → 重试
     → interpretation → lite dashboard → report
```

| 主题 | 路径 |
|------|------|
| 工具 Schema | `tools/schemas.py`（FastQC/Trimmomatic/MEGAHIT/MetaBAT2/HUMAnN3/Kraken2…） |
| 引擎参数手递 | `execution/workflow_params.py` → `outdir/workflow/params.yaml` |
| 引擎启动 | `execution/engine.py`（读 params，禁止 LLM 自由 shell） |
| 自愈循环 | `execution/self_heal.py`（OOM 增内存、缺库/缺文件分类） |
| 技能契约 | `skills/contracts.py` · `tool_specialist.py` |
| 步骤缓存 | `execution/step_cache.py` |

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → export_dag(+params.yaml + resource_estimate) → workflow_agent → contract → HITL
  → swarm|external engine → validate → quality → HITL(runtime) → self-heal*
  → visualization → xai → report
```

**策略**：Agent 理解需求并产出校验后的配置；底层调度已模块化的 Nextflow / Snakemake（或带 step cache 的 LangGraph）。
