# Reference databases (not shipped in git)

Place or symlink databases here:

```
database/
├── kraken_db/     # Kraken2 / Bracken index
├── gtdb/          # GTDB-Tk data
└── eggnog/        # eggNOG-mapper database
```

Configure absolute paths in `config/default.yaml`:

```yaml
paths:
  host_index: /path/to/hg38
  kraken2_db: /path/to/database/kraken_db
  metaphlan_db: /path/to/metaphlan_db
  gtdb: /path/to/database/gtdb
  eggnog: /path/to/database/eggnog
```

Mock mode (`--mode mock`) does not require these databases.
