# Metagenomic Research Agent

**版本** `0.14.0` · 技能契约 + 步骤缓存 · CoT 生物推理审计 · 轻量 Dashboard · 生产资源预估 / `-resume`。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "分析肥胖患者肠道菌群变化"
# 审计推理链
open ./results/bio_reasoning_audit.json
# 轻量仪表盘（推荐起本地静态服务）
cd results && python -m http.server 8765
pytest -q && meta-agent version
```

## 流水线

```
Router → Bio Reasoning (CoT+citations) → Supervisor → Tool Specialist (contracts)
  → resource estimate → HITL → Swarm (step cache) → HITL(runtime)
  → Critic → Literature → Viz (lite) → Report
```

## 文档

| 文档 | 用途 |
|------|------|
| [docs/USAGE.md](docs/USAGE.md) | CLI / 配置 / 产物 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构 |
| [docs/METHODS.md](docs/METHODS.md) | 论文 Methods |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 能力对照与生产提示 |
| [CHANGELOG.md](CHANGELOG.md) | 版本 |

## License

MIT
