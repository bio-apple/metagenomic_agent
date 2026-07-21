# Metagenomic Research Agent

**版本** `0.13.0` · Bio Reasoning 规划前推理 · 多智能体端到端发现 · 交互可视化 · 抗幻觉证据链 · 容器沙盒。

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
  -q "分析肥胖患者肠道菌群变化"

open ./results/bio_reasoning.md
open ./results/interactive_dashboard.html
pytest -q && meta-agent version
```

| Mode | 说明 |
|------|------|
| `mock` | CI/演示 |
| `docker` / `apptainer` | **推荐** biocontainers |
| `conda` / `local` | 本机工具 |

## 流水线（Biological Reasoning 优先）

```
User → Router → Bio Reasoning → Supervisor (PM)
  → Tool Specialist → Plan Validator → Workflow
  → HITL → Swarm (QC/Tax/Asm/Function/Stats)
  → HITL(runtime) → Critic → Literature → Viz → Report
```

不再是「LLM + Pipeline Wrapper」，而是：需求理解 → **生物学推理** → 工作流规划 → 工具执行 → 结果解释。

## 核心能力

| 能力 | 要点 |
|------|------|
| Bio Reasoning | 推断研究目标、assay、流程步骤、组装策略、下一步实验 |
| 多智能体 | PM/QC/Taxonomy/Assembly/Function/Stats/Publication 草稿 |
| HITL 多方案 | A/B/C（研究设计、缺分组、宿主污染） |
| 抗幻觉证据链 | GTDB/NCBI 锚定 + 丰度/p·q/DB ID/PMID |
| 摘要上下文 | LLM 不读原始序列 |
| 可复现导出 | `.nf`/`.smk` + seed + Methods |
| 交互可视化 | Plotly 组成/多样性/PCoA/Heatmap |

## 文档

| 文档 | 用途 |
|------|------|
| [docs/USAGE.md](docs/USAGE.md) | CLI / 配置 / 产物 / 排障 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 模块结构 |
| [docs/METHODS.md](docs/METHODS.md) | 论文 Methods |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 对照开发者建议的路线图 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |
| [database/README.md](database/README.md) | 参考库路径 |

## 局限

见 [docs/ROADMAP.md](docs/ROADMAP.md) 与 [docs/METHODS.md](docs/METHODS.md)。`mock` 不可作生物学结论。

## License

MIT
