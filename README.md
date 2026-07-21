# Metagenomic Research Agent v0.5

面向顶刊级严谨性的三阶段升级：**Skill/Contract → gLM 路由 → 生物学上下文验证 + CWL 可复现包**。

详见 [`docs/OPTIMIZATION_PROPOSAL_IMPL.md`](docs/OPTIMIZATION_PROPOSAL_IMPL.md) 与 [`docs/METHODS.md`](docs/METHODS.md)。

## 主链路

```
parse → supervisor → contract_check → HITL → swarm
      → validate → self-heal* → critic → literature → report(+CWL)
```

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut metagenome biomarker discovery"
pytest -q
```

关键产物：`contract_check.json`、`taxonomy_routing.json`、`biological_context.json`、`reproducibility/meta_agent.cwl`。
