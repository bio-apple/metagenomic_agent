# Demo data（审稿 / 本地一键复现）

仓库内置的极小 paired FASTQ（每样本约 520 B），**不依赖参考库**，配合 `--mode mock` 即可跑通全流程。

| 路径 | 说明 |
|------|------|
| `fastq/` | 4 个样本 × R1/R2（`ibd_*` / `ctrl_*`） |
| `metadata.tsv` | `sample_id` + `group`（IBD vs Control） |

一键复现见仓库根目录：`bash scripts/reproduce_demo.sh`

```bash
pip install -e ".[dev]"
meta-agent run \
  -i examples/demo_data/fastq \
  --metadata examples/demo_data/metadata.tsv \
  -o ./results/demo \
  --mode mock --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"
```

预期产物（节选）：`results/demo/final_report.html`、`results/demo/evaluation/`（含 CAMI toy / MetaAgentScore）、`biomarkers/`。

> Mock 输出仅用于软件与流水线复现，**不可当作生物学结论**。真实分析请按 [database/README.md](../../database/README.md) 构建参考库后使用 `docker` / `apptainer` 模式。
