# 开发者路线图（对照建议）

对照开发者建议与当前 **v0.15**。状态：`Done` / `Partial` / `Planned`。

## 目标架构

```
User → Requirement Understanding → Biological Reasoning (CoT + citations)
     → Workflow Planning (Schema + skill contracts) → params.yaml
     → Tool Execution (Nextflow/Snakemake / cache / -resume) → Self-heal
     → Result Interpretation → Lite Dashboard + Report
```

| 建议 | 状态 | 现状 |
|------|------|------|
| Dag/Workflow Engine 底座 | **Done** | Agent 写 `params.yaml`；`execution.engine=nextflow\|snakemake` 调度；默认仍可 LangGraph |
| 禁止 LLM 自由 shell | **Done** | 策略写入 params + sandbox；命令仅为模板 |
| 工具 JSON Schema / Pydantic | **Done** | `tools/schemas.py` + Specialist/Sandbox 校验 |
| 自愈：日志→改参→重试 | **Done** | OOM 增内存；缺 DB/文件分类；重写 params 后 rerun |
| 技能契约（非自由 CLI） | **Done** | `skills/registry` + Tool Specialist |
| 中间结果缓存 / 断点续跑 | **Done** | `step_cache` + nf `-resume` / smk `--rerun-incomplete` |
| Bio CoT + 外部知识引用 | **Done** | `bio_cot_examples` + citations audit |
| 轻量 Dashboard | **Done** | `visualization.lite` |
| FastQC/MultiQC 原生 process | Partial | Schema 已备；nf process 粒度仍以 Agent 封装为主 |
| 向量 Memory（Chroma/FAISS） | Planned | ContextMemory 文件 |
| CAMI/HMP Benchmark | Partial | smoke benchmarks |
| Conversation Agent | Partial | CLI/API |

## 生产提示

```bash
# 外部引擎（Agent 先写出 outdir/workflow/params.yaml）
# config: execution.engine: nextflow | snakemake
nextflow run workflow/nextflow/main.nf -params-file results/workflow/params.json -resume
snakemake -s workflow/Snakefile --configfile results/workflow/snakemake_config.yaml --rerun-incomplete -j 8

# 轻量仪表盘
cd results && python -m http.server 8765
```

最终目标：**Autonomous Multi-Agent System for End-to-End Metagenomic Discovery**。
