# Metagenomic Research Agent

**版本** `0.23.0` · 宏基因组 AI Scientist（规划 · 执行 · 审稿 · KG · 可复现报告）。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "分析肥胖患者肠道菌群变化"
pytest -q && meta-agent version

meta-agent serve --host 127.0.0.1 --port 8000
open http://127.0.0.1:8000/ui
# 或：docker compose up --build
```

## 流水线（摘要）

```
Planner → HITL → Swarm(QC/Tax/Func/Resistance/Stats)
  → Critic → Literature → Evidence → Reviewer → Reflection → Report
```

## 文档（仅此四份 + 版本记录）

| 文档 | 用途 |
|------|------|
| [docs/USAGE.md](docs/USAGE.md) | CLI / API / 配置 / 产物 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与设计（开发者必读） |
| [docs/DEPLOY_LINUX.md](docs/DEPLOY_LINUX.md) | Linux ≥256 GB 部署 |
| [database/README.md](database/README.md) | 参考库 / 知识目录 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |

## License

MIT
