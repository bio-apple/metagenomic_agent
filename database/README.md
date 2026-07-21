# Reference databases & Knowledge Layer

挂载全量库或使用包内 curated stub（`src/metagenomic_agent/rag/data/curated_bio_index.json`）。
`mock` 可不挂载。

## 推荐目录契约

```text
database/
├── taxonomy/       # GTDB、NCBI Taxonomy dumps / kraken2 DB 符号链接
├── function/       # KEGG / eggNOG / DIAMOND protein DB
├── arg/            # CARD (for RGI) / DeepARG models
├── virulence/      # VFDB
├── pathway/        # pathway maps / HUMAnN ChocoPhlAn
├── microbiome/     # GMrepo / UHGG 等目录索引
├── literature/     # 可选本地 PMID JSON 缓存
├── kraken_db/      # → paths.kraken2_db
├── gtdb/           # → paths.gtdb
└── eggnog/         # → paths.eggnog
```

| Config key | Purpose |
|------------|---------|
| `paths.host_index` | 宿主 Bowtie2 index |
| `paths.kraken2_db` | Kraken2 |
| `paths.metaphlan_db` | MetaPhlAn |
| `paths.gtdb` | GTDB-Tk |
| `paths.eggnog` | eggNOG |
| `paths.diamond_db` | DIAMOND |
| `paths.glm_weights` / `glm_inference_cmd` | gLM |

## RAG

- 模式：`rag.mode: keyword | semantic | hybrid`（默认 hybrid）
- 权威库：`rag.authority_dbs`（GTDB/NCBI/KEGG/UniProt/CARD）
- 解读抗幻觉：`interpretation.require_grounding` + `require_evidence_chain`

CLI 见 [docs/USAGE.md](../docs/USAGE.md)；大内存部署见 [docs/DEPLOY_LINUX.md](../docs/DEPLOY_LINUX.md)。
