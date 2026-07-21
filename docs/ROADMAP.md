# 开发者路线图（对照建议）

对照开发者建议与当前 **v0.14**。状态：`Done` / `Partial` / `Planned`。

## 目标架构

```
User → Requirement Understanding → Biological Reasoning (CoT + citations)
     → Workflow Planning (skill contracts) → Tool Execution (cache / -resume)
     → Result Interpretation → Lite Dashboard + Report
```

| 建议 | 状态 | 现状 |
|------|------|------|
| 技能契约（非自由 CLI） | **Done** | `skills/registry` + Tool Specialist 绑定 I/O 契约 |
| 中间结果缓存 / 断点续跑 | **Done** | `execution/step_cache.py` → `outdir/cache/steps`；节点 `cached` |
| Bio CoT + 外部知识引用 | **Done** | `knowledge/bio_cot_examples.json`；强制 citations；`bio_reasoning_audit.json` |
| 轻量 Dashboard | **Done** | `visualization.lite=true`：摘要 + 按需 fetch JSON |
| 资源预估 | **Done** | `resource_estimate.json`（墙钟/内存/磁盘 + 警告） |
| Nextflow/Snakemake resume | **Done** | nf `-resume`；smk `--rerun-incomplete` |
| FastQC/MultiQC / HUMAnN3 | Partial | 主路径 fastp/DIAMOND；原生封装 Planned |
| 向量 Memory（Chroma/FAISS） | Planned | 现为 ContextMemory 文件 |
| CAMI/HMP Benchmark | Partial | smoke benchmarks |
| Conversation Agent | Partial | CLI/API |

## 生产提示

```bash
# 轻量仪表盘需静态服务（file:// 下 fetch 受限）
cd results && python -m http.server 8765
# 打开 http://127.0.0.1:8765/interactive_dashboard.html

# 外部引擎续跑
# config: execution.engine: nextflow | snakemake
```

最终目标：**Autonomous Multi-Agent System for End-to-End Metagenomic Discovery**。
