# Reference databases

将索引放在本目录，或在 `config/default.yaml` → `paths.*` 写绝对路径：

```text
database/
├── kraken_db/      # paths.kraken2_db
├── gtdb/           # paths.gtdb
└── eggnog/         # paths.eggnog
```

| Key | Purpose |
|-----|---------|
| `paths.host_index` | 宿主 Bowtie2 index |
| `paths.metaphlan_db` | MetaPhlAn |
| `paths.diamond_db` | DIAMOND |
| `paths.glm_weights` / `glm_inference_cmd` | gLM |

包内 curated 生物索引：`src/metagenomic_agent/rag/data/curated_bio_index.json`（GTDB/NCBI/KEGG/UniProt/CARD/VFDB stub）。全量库可替换并保持字段名。`mock` 可不挂载库。

CLI 与配置详见 [docs/USAGE.md](../docs/USAGE.md)。
