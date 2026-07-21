# Metagenomic Research Agent

**版本** `0.7.0` · 自主宏基因组科研智能体（LangGraph）：契约驱动 · 生物库 RAG · Evidence Table · PCoA/LEfSe-like · PI 复审 · CWL 可复现。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 主链路

```
parse → supervisor → export_dag → contract_check → HITL → swarm
      → validate → quality_scores → self-heal*
      → critic → literature → pi_review* → visualization → report
```

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

pytest -q
meta-agent version
```

## 运行模式

| Mode | 说明 |
|------|------|
| `mock` | 无数据库/二进制，结构完整演示（CI 默认） |
| `local` | 本机已安装工具 |
| `conda` | 按 `linux.conda_envs` 切环境 |
| `docker` | biocontainers / 自定义镜像 |

## 关键产物

| 路径 | 含义 |
|------|------|
| `workflow/dag.json` | 可移植分析 DAG |
| `contract_check.json` | 技能契约检查 |
| `evidence/evidence_table.md` | 物种–疾病–PMID 证据表 |
| `quality/quality_scores.json` | 数据质量评分 |
| `biomarkers/` | MWU、LEfSe-like、ANCOM-like |
| `report/figures/` | PCoA、共现、Volcano、Sankey 等 |
| `report/manuscript/` | 投稿分节草稿 |
| `reproducibility/` | CWL + run_manifest |
| `context/context.json` | 项目 Memory |

## 文档

| 文档 | 用途 |
|------|------|
| [docs/README.md](docs/README.md) | 索引 |
| [docs/USAGE.md](docs/USAGE.md) | CLI / API / 配置 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与能力一览 |
| [docs/METHODS.md](docs/METHODS.md) | 论文 Methods 说明 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |
| [database/README.md](database/README.md) | 参考库路径 |

## 局限（发表前披露）

- 默认差异丰度为 MWU + BH-FDR；LEfSe-like / ANCOM-like 为 Python 近似，非正式 R 包。
- 生物库 RAG 默认 curated 索引；全量 GTDB/CARD/KEGG 需自备挂载。
- gLM 需配置 `paths.glm_weights` 与可选 `glm_inference_cmd`。
- `mock` 结果不可作生物学结论。

## License

MIT
