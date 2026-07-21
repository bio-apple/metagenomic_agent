# Reference databases

Place indexes under this tree, or point `config/default.yaml` → `paths.*` to absolute locations:

```text
database/
├── kraken_db/          # paths.kraken2_db
├── gtdb/               # paths.gtdb
├── eggnog/             # paths.eggnog
└── (optional) host BT2 index → paths.host_index
```

Also configure:

| Key | Purpose |
|-----|---------|
| `paths.metaphlan_db` | MetaPhlAn database |
| `paths.diamond_db` | DIAMOND functional DB |
| `paths.glm_weights` | gLM weights (empty → stub/mock adapter) |

`mock` mode and empty directories fall back to simulated outputs. No private Docker images are required for demos.

See [docs/USAGE.md](../docs/USAGE.md) for runtime modes (`local` / `conda` / `docker`).
