# Demo data (review / local one-click reproduction)

Bundled minimal paired FASTQ (≈520 B per sample). **No reference databases required**; with `--mode mock` the full pipeline exercises end-to-end.

| Path | Description |
|------|-------------|
| `fastq/` | 4 samples × R1/R2 (`ibd_*` / `ctrl_*`) |
| `metadata.tsv` | `sample_id` + `group` (IBD vs Control) |

One-click reproduction from the repository root: `bash scripts/reproduce_demo.sh`

```bash
pip install -e ".[dev]"
meta-agent run \
  -i examples/demo_data/fastq \
  --metadata examples/demo_data/metadata.tsv \
  -o ./results/demo \
  --mode mock --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"
```

Expected outputs (selected): `results/demo/final_report.html`, `results/demo/evaluation/` (CAMI toy / MetaAgentScore), `biomarkers/`.

> Mock outputs are for software and pipeline reproducibility only and **must not be treated as biological conclusions**. For real analyses, build reference databases per [database/README.md](../../database/README.md) and use `docker` / `apptainer` mode.
