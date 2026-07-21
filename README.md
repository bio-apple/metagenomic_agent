# Metagenomic Research Agent

**版本** `0.12.0` · 容器沙盒多智能体宏基因组平台：抗幻觉证据链、摘要驱动长上下文、可复现工作流导出、交互式 Plotly 分析。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 快速开始

```bash
git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

meta-agent run \
  -i tests/fixtures/fastq \
  -o ./results \
  --mode mock \
  --yes \
  -q "IBD gut metagenome biomarker discovery"

# 浏览器打开交互视图
open ./results/interactive_dashboard.html   # 或 final_report.html
pytest -q && meta-agent version
```

| Mode | 说明 |
|------|------|
| `mock` | CI/演示，无库无二进制 |
| `docker` / `apptainer` | **推荐** biocontainers（Apple Silicon 用 `linux/amd64`） |
| `conda` / `local` | 本机工具；失败时可自愈切容器 |

## 流水线

```
parse → Router → Supervisor → Tool Specialist → Plan Validator
  → DAG/Workflow → contract → HITL → swarm
  → validate → quality → self-heal* → critic → literature
  → PI* → visualization → XAI → report
```

## 核心能力（摘要）

| 能力 | 要点 | 主要产物 / 配置 |
|------|------|----------------|
| 容器沙盒与自愈 | 工具走 Docker/Apptainer；OOM/架构错误自动恢复 | `sandbox.*` |
| 抗幻觉 | 菌种须 GTDB/NCBI 锚定；陈述带丰度/p·q/DB ID/PMID | `evidence/claims.*`；`interpretation.*` |
| 长上下文 | LLM 只读统计元数据，不进原始序列 | `context/pipeline_summary.json`；`summary.*` |
| 可复现 | 事后导出 seed + `.nf`/`.smk` + config 快照 | `workflow/reproducible.*`；`reproducibility.*` |
| 交互可视化 | 组成 / Alpha·Beta / PCoA / Heatmap / Volcano；q 滑块 | `interactive_dashboard.html`；`visualization.*` |

## 文档

| 文档 | 用途 |
|------|------|
| [docs/USAGE.md](docs/USAGE.md) | CLI、API、配置、排障、产物路径 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 多智能体与模块结构 |
| [docs/METHODS.md](docs/METHODS.md) | 论文 Methods 可引用说明 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |
| [database/README.md](database/README.md) | 参考库挂载路径 |

运行时知识（Supervisor 读取，非用户手册）：`src/metagenomic_agent/knowledge/best_practices.md`。

## 局限

- 部分病毒/分类工具可为路由注册而未安装；`mock` 不可作生物学结论。
- 差异检验默认轻量（含 LEfSe/ANCOM 近似）；XAI 为组间分离度归因，非完整 SHAP。
- 生物/工作流 RAG 为 curated 语料；全量库与 nf-co.re 需自备。

## License

MIT
