# Metagenomic Research Agent v0.4

四角色优化后的宏基因组智能体：**AI Agent / 生信专家 / 工程 / 科研评价**。

详细方法学说明见 [`docs/METHODS.md`](docs/METHODS.md)。

## 本版增强

| 角色 | 落地 |
|------|------|
| AI Agent | 结构化 `AgentMessage`、HITL 节点、Pydantic 规划校验、Monitor JSONL、统一 self-heal 重试 |
| 生信 | MAG CheckM 门槛、DAS-Tool 风格共识、Mann-Whitney+BH-FDR（诚实声明）、扩展 Gut KB |
| 工程 | GitHub Actions CI、recovery 前缀修复、engine 真正可选调度、版本对齐 |
| 科研 | 动态 `methods.md`、完整 `reproduce.sh`、`evaluation.metrics`、golden 评测测试 |

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "Analyze IBD metagenomes and identify microbial biomarkers"
pytest -q
```

产物含 `logs/events.jsonl`、`report/methods.md`、`report/reproduce.sh`。
