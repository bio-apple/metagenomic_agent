# Metagenomic Research Agent

**版本** `0.8.0` · **专业化多智能体**：Router · Tool Specialist · Plan Validator · Workflow RAG · XAI。

## 多智能体主链路

```
parse → Router → Supervisor → Tool Specialist → Plan Validator
      → export_dag → Workflow Agent → contract → HITL → swarm
      → validate → quality → self-heal* → critic → literature
      → PI* → visualization → XAI → report
```

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut metagenome biomarker discovery"
pytest -q
```

## 文档

[docs/README.md](docs/README.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/USAGE.md](docs/USAGE.md) · [docs/METHODS.md](docs/METHODS.md)

## License

MIT
