# Metagenomic Research Agent

**版本** `0.20.0` · LangGraph 多智能体宏基因组分析 · 关键 HITL（含 Web/API 异步审批）。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "分析肥胖患者肠道菌群变化"
open ./results/bio_reasoning_audit.json
cd results && python -m http.server 8765   # 轻量仪表盘
pytest -q && meta-agent version
```

API 异步 HITL：

```bash
meta-agent serve --host 127.0.0.1 --port 8000
# POST /analyze  hitl_mode=async → GET/POST /runs/{run_id}/hitl
```

## 流水线

```
Router → Planner → HITL → Executor (cluster → BioContainers + checkpoints)
  → QC/Critic → Reporter → Report
```

## 文档

| 文档 | 用途 |
|------|------|
| [docs/USAGE.md](docs/USAGE.md) | CLI / API / 配置 / 产物 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与 Methods 要点 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |
| [database/README.md](database/README.md) | 参考库路径 |

## License

MIT
