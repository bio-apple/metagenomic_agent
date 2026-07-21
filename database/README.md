# Reference databases

Place indexes here or set absolute paths in `config/default.yaml` → `paths.*`:

```text
database/
├── kraken_db/     # paths.kraken2_db
├── gtdb/          # paths.gtdb
└── eggnog/        # paths.eggnog
```

| Key | Purpose |
|-----|---------|
| `paths.host_index` | Host Bowtie2 index（Plan Validator 可能要求） |
| `paths.metaphlan_db` | MetaPhlAn |
| `paths.diamond_db` | DIAMOND |
| `paths.glm_weights` | gLM 权重 |
| `paths.glm_inference_cmd` | 外部 gLM 命令模板 |

生物知识检索默认用包内 curated 索引（`src/metagenomic_agent/rag/data/`）。工具领域路由见 `knowledge/tool_domain_kb.json`。

`mock` 模式可不挂载数据库。详见 [docs/USAGE.md](../docs/USAGE.md)。
