> English: [README.md](README.md)

# 演示数据（审稿 / 本地一键复现）

内置最小配对 FASTQ（每样本约 ≈520 B）。**无需参考数据库**；配合 `--mode mock` 可端到端演练完整流水线。

| Path | Description |
|------|-------------|
| `fastq/` | 4 个样本 × R1/R2（`ibd_*` / `ctrl_*`） |
| `metadata.tsv` | `sample_id` + `group`（IBD vs Control） |

在仓库根目录一键复现：`bash scripts/reproduce_demo.sh`

```bash
pip install -e ".[dev]"
meta-agent run \
  -i examples/demo_data/fastq \
  --metadata examples/demo_data/metadata.tsv \
  -o ./results/demo \
  --mode mock --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"
```

预期输出（节选）：`results/demo/final_report.html`、`results/demo/evaluation/`（CAMI toy / MetaAgentScore）、`biomarkers/`。

> Mock 输出仅用于软件与流水线可重复性，**不得视为生物学结论**。真实分析请按 [database/README.md](../../database/README.md) 构建参考库，并使用 `docker` / `apptainer` 模式。
