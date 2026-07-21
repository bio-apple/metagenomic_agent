# Metagenomic Research Agent

**版本** `0.7.0` · 自主宏基因组科研平台：生物库 RAG（含 TF-IDF）、Evidence Table、真实 PCoA/共现/LEfSe-like、PI 复审、契约硬失败、gLM 外部推理钩子。

## 主链路

```
parse → supervisor → export_dag → contract_check → HITL → swarm
      → validate → quality → self-heal* → critic → literature
      → PI review* → visualization → report(+manuscript/CWL)
```

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut metagenome biomarker discovery"
pytest -q
```

## 文档

[docs/README.md](docs/README.md) · [docs/PROPOSAL_2026_IMPL.md](docs/PROPOSAL_2026_IMPL.md) · [CHANGELOG.md](CHANGELOG.md)

## License

MIT
