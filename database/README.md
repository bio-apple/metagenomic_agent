# Reference databases

Place indexes under this tree, or set absolute paths in `config/default.yaml` → `paths.*`:

```text
database/
├── kraken_db/     # paths.kraken2_db
├── gtdb/          # paths.gtdb
└── eggnog/        # paths.eggnog
```

| Key | Purpose |
|-----|---------|
| `paths.host_index` | Host Bowtie2 index |
| `paths.metaphlan_db` | MetaPhlAn DB |
| `paths.diamond_db` | DIAMOND functional DB |
| `paths.glm_weights` | gLM weights（空则 mock/桩） |
| `paths.glm_inference_cmd` | 外部推理命令模板 |

生物知识检索默认使用包内 curated 索引（`src/metagenomic_agent/rag/data/`），不依赖本目录全量转储。

`mock` 模式可在无数据库时运行。详见 [docs/USAGE.md](../docs/USAGE.md)。
