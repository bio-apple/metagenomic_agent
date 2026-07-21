# Metagenomic Research Agent

**版本** `0.6.0` · 面向科研智能体：生物数据库 RAG、文献 Evidence Table、显式 Workflow DAG、质量评分与投稿级手稿骨架。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 主链路

```
parse → supervisor → export_dag → contract_check → HITL → swarm
      → validate → quality_scores → self-heal* → critic
      → literature(+Evidence) → visualization → report(+manuscript/CWL)
```

## 快速开始

```bash
pip install -e ".[dev]"
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut metagenome biomarker discovery"
pytest -q
```

## 关键产物（v0.6）

| 路径 | 含义 |
|------|------|
| `workflow/dag.json` + `dag.mmd` | 显式 DAG（可移交 Snakemake/Nextflow） |
| `evidence/evidence_table.md` | 物种–疾病–PMID–Effect 证据表 |
| `quality/quality_scores.json` | Coverage / Assembly / Contamination / Completeness / Overall |
| `report/figures/` · `report/tables/` | 可视化与表格 |
| `report/manuscript/` | Introduction…References 草稿 |
| `context/context.json` | 项目 Memory（host/platform/read_length） |

## 文档

见 [docs/README.md](docs/README.md)。METHODS：[docs/METHODS.md](docs/METHODS.md)。

## 诚实边界

- 生物库 RAG 默认使用**精炼 curated 索引**；挂载完整 GTDB/CARD/KEGG 转储前请勿当作全库检索。
- 手稿为模板草稿，投稿前需领域专家修订。
- 默认统计仍为 MWU + BH-FDR。

## License

MIT
