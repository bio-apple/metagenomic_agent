# Metagenomic Research Agent

**版本** `0.5.0` · 契约驱动的宏基因组 AI 智能体：Skill/Contract → gLM 智能路由 → 生物学上下文验证 → CWL 可复现包。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 它做什么

用自然语言研究问题驱动端到端 shotgun 宏基因组分析：自动规划 DAG、执行 QC/分类/功能/（可选）组装分箱、统计与文献辅助，并输出可复现报告。

```
parse → supervisor → contract_check → HITL → swarm
      → validate → self-heal* → critic → literature → report(+CWL)
```

## 快速开始

```bash
git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 无数据库演示（推荐先跑通）
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
| `mock` | 不调用真实生信二进制，产出结构完整的演示结果（CI/本地验证） |
| `local` | 调用本机已安装工具 |
| `conda` | 按 `config/default.yaml` 中 `linux.conda_envs` 切环境 |
| `docker` | 通过 biocontainers / 自定义镜像运行 |

人机确认：默认配置里 `hitl.auto_confirm` 可能为 `true`（便于 CI）。生产交互请设为 `false`，或用 CLI `--yes` 跳过确认。

## 配置要点

主配置：[`config/default.yaml`](config/default.yaml)

- `routing.enable_glm` / `dual_path` / `epsilon`：gLM 与 ε-greedy 工具选择
- `paths.*`：宿主索引、Kraken2、GTDB、gLM 权重等
- `pipeline.enable_assembly`：是否启用组装–分箱–CheckM
- `validation.*`：技术与肠道标志物阈值
- `llm.*`：OpenAI 兼容端点（DeepSeek / vLLM / Ollama）

数据库放置见 [`database/README.md`](database/README.md)。

## 关键产物

| 路径 | 含义 |
|------|------|
| `contract_check.json` | 剧本与技能前置契约结果 |
| `taxonomy_routing.json` | 读长路由 / 双路融合决策 |
| `biological_context.json` | 上下文生物学警告 |
| `report/methods.md` / `reproduce.sh` | 方法学与一键复现命令 |
| `reproducibility/meta_agent.cwl` | CWL 可复现包 |
| `logs/events.jsonl` | 结构化运行事件 |
| `report/final_report.md` | 综合报告入口 |

## HTTP API

```bash
meta-agent serve --host 127.0.0.1 --port 8000
# GET  /health
# POST /analyze  { "input_path", "outdir", "query", "mode", ... }
```

## 文档导航

| 文档 | 用途 |
|------|------|
| [docs/README.md](docs/README.md) | 文档索引 |
| [docs/USAGE.md](docs/USAGE.md) | CLI / API / 配置详解 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 当前实现架构（v0.5） |
| [docs/METHODS.md](docs/METHODS.md) | 论文 Methods 可引用说明 |
| [docs/OPTIMIZATION_PROPOSAL_IMPL.md](docs/OPTIMIZATION_PROPOSAL_IMPL.md) | v0.5 能力落地对照 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更 |

## 局限（发表前务必披露）

- 默认差异丰度是 **Mann–Whitney U + BH-FDR**，不是 ANCOM-BC / MaAsLin2 / LEfSe。
- gLM（microCafe / MicroRAG）默认走适配层；未配置 `paths.glm_weights` 时为 mock/桩实现。
- `mock` 模式仅用于工程与演示，不可作为生物学结论依据。

## License

MIT
