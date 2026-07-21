# Reference Databases: Directory Contract and Build Guide

The repository `database/` directory holds **full reference databases** (or symlinks).  
The in-package RAG stub (`src/metagenomic_agent/rag/data/curated_bio_index.json`) is for interpretation / anti-hallucination retrieval only and **cannot replace** runtime libraries such as Kraken2 / GTDB-Tk.

| Mode | Requires this directory? |
|------|--------------------------|
| `mock` | No |
| `local` / `conda` / `docker` / `apptainer` | Yes (at least taxonomy + host; functional/ARG as needed) |

Skeleton helper script: [scripts/build_databases.sh](../scripts/build_databases.sh) (you must provide network and disk).

---

## 1. Recommended layout and config mapping

Create under the repository root or `/ref/databases`:

```text
database/                         # or /ref/databases → wired into config paths.*
├── host/
│   └── hg38/                     # Bowtie2 index prefix: hg38
├── kraken_db/                    # Kraken2 standard DB (hash.k2d, etc.)
├── metaphlan_db/                 # MetaPhlAn database directory
├── gtdb/                         # GTDB-Tk release data root
├── eggnog/                       # eggNOG-mapper data
├── diamond/                      # DIAMOND .dmnd
├── humann/                       # chocophlan + uniref (optional)
├── arg/
│   ├── card/                     # CARD JSON (RGI load)
│   └── deeparg/                  # DeepARG models (optional)
├── virulence/
│   └── vfdb/                     # VFDB protein/nucleotide (optional DIAMOND)
├── taxonomy/                     # optional: NCBI taxdump / GTDB metadata mirror
├── function/                     # optional: local KEGG mirror notes
├── pathway/                      # optional: HUMAnN pathway
├── microbiome/                   # optional: UHGG and related indexes
└── literature/                   # optional: local PMID JSON cache
```

In `config/default.yaml` or `config/site.yaml`:

```yaml
paths:
  host_index: "/ref/databases/host/hg38"          # Bowtie2 prefix, without .1.bt2 suffix
  kraken2_db: "/ref/databases/kraken_db"
  metaphlan_db: "/ref/databases/metaphlan_db"
  gtdb: "/ref/databases/gtdb"
  eggnog: "/ref/databases/eggnog"
  diamond_db: "/ref/databases/diamond/nr.dmnd"  # or uniref90.dmnd
```

Relative paths are resolved against the **runtime cwd**; use **absolute paths** in production.

Rough disk estimates (SSD/parallel FS; avoid slow NFS on hot paths):

| Database | Approx. size |
|----------|--------------|
| Host hg38 Bowtie2 | ~4–8 GB |
| Kraken2 Standard | ~50–100 GB+ (version-dependent) |
| MetaPhlAn | ~5–15 GB |
| GTDB-Tk r214+ | ~50–80 GB |
| eggNOG | ~50 GB+ |
| DIAMOND UniRef | 20–200 GB depending on DB |
| CARD | <1 GB |

---

## 2. Build steps (by priority)

Run the following on Linux x86_64 with the corresponding tools or BioContainers installed.  
Example `DB_ROOT`: `export DB_ROOT=/ref/databases` or `$(pwd)/database`.

### 2.1 Host decontamination index (`paths.host_index`) — **strongly recommended**

```bash
export DB_ROOT=/ref/databases
mkdir -p "$DB_ROOT/host" && cd "$DB_ROOT/host"

# Download human reference (example GRCh38 primary chromosomes; follow institutional policy)
# wget -O hg38.fa.gz "https://..."
# gunzip -c hg38.fa.gz > hg38.fa

# Build Bowtie2 index (prefix = paths.host_index)
bowtie2-build --threads 16 hg38.fa hg38
# Products: hg38.1.bt2 … → paths.host_index: "$DB_ROOT/host/hg38"
```

Container example:

```bash
apptainer exec docker://quay.io/biocontainers/bowtie2:2.5.3--py39hd2f008b_0 \
  bowtie2-build --threads 16 hg38.fa hg38
```

### 2.2 Kraken2 (`paths.kraken2_db`) — **required for taxonomy**

**Option A: download official prebuilt Standard (recommended)**

```bash
mkdir -p "$DB_ROOT/kraken_db" && cd "$DB_ROOT/kraken_db"
# Check current mirrors / versions: https://benlangmead.github.io/aws-indexes/k2
# Example (URL changes with releases; follow the official site):
# wget https://genome-idx.s3.amazonaws.com/kraken/k2_standard_YYYYMMDD.tar.gz
# tar -xzf k2_standard_*.tar.gz -C "$DB_ROOT/kraken_db"
# After extract the directory should contain: hash.k2d  opts.k2d  taxo.k2d
```

**Option B: build with `kraken2-build`**

```bash
DB="$DB_ROOT/kraken_db"
mkdir -p "$DB"
kraken2-build --download-taxonomy --db "$DB"
kraken2-build --download-library bacteria --db "$DB"   # optionally archaea/viral/human
kraken2-build --download-library archaea --db "$DB"
# If human reads are removed via host filtering, human need not be in the DB
kraken2-build --build --db "$DB" --threads 32
# Optional: bracken-build -d "$DB" -t 32 -k 35 -l 150
```

Validate:

```bash
ls "$DB_ROOT/kraken_db"/hash.k2d "$DB_ROOT/kraken_db"/taxo.k2d
kraken2 --db "$DB_ROOT/kraken_db" --threads 4 --paired R1.fq R2.fq --report /tmp/t.kreport >/dev/null
```

Config: `paths.kraken2_db: "$DB_ROOT/kraken_db"`.

### 2.3 MetaPhlAn (`paths.metaphlan_db`)

```bash
mkdir -p "$DB_ROOT/metaphlan_db"
# After installing metaphlan:
metaphlan --install --bowtie2db "$DB_ROOT/metaphlan_db"
# Or a versioned index (follow MetaPhlAn docs):
# metaphlan --install --index mpa_vOct22_CHOCOPhlAnSGB_202212 --bowtie2db "$DB_ROOT/metaphlan_db"
```

Config: `paths.metaphlan_db: "$DB_ROOT/metaphlan_db"`.

### 2.4 GTDB-Tk (`paths.gtdb`) — **MAG taxonomy**

```bash
mkdir -p "$DB_ROOT/gtdb" && cd "$DB_ROOT/gtdb"
# Follow https://ecogenomics.github.io/GTDBTk/installing/index.html
# Download the matching release gtdbtk_data.tar.gz (large)
# tar -xzf gtdbtk_rXXXvX_data.tar.gz -C "$DB_ROOT/gtdb"
# Extracted tree usually includes: taxonomy/  markers/  masks/  metadata/ …

export GTDBTK_DATA_PATH="$DB_ROOT/gtdb"   # or the release subdirectory
```

Config: `paths.gtdb: "$DB_ROOT/gtdb"` (must match `GTDBTK_DATA_PATH`).

### 2.5 eggNOG (`paths.eggnog`) — **functional annotation**

```bash
mkdir -p "$DB_ROOT/eggnog" && cd "$DB_ROOT/eggnog"
# Use eggnog-mapper's downloader (eggnog-mapper must be installed):
download_eggnog_data.py -y --data_dir "$DB_ROOT/eggnog"
# Or follow http://eggnog5.embl.de for diamond DB + annotations
```

Config: `paths.eggnog: "$DB_ROOT/eggnog"`.

### 2.6 DIAMOND (`paths.diamond_db`)

```bash
mkdir -p "$DB_ROOT/diamond" && cd "$DB_ROOT/diamond"
# Example: UniRef90 FASTA → dmnd
# wget .../uniref90.fasta.gz && gunzip -c uniref90.fasta.gz > uniref90.fa
diamond makedb --in uniref90.fa --db uniref90 --threads 32
# Product: uniref90.dmnd
```

Config: `paths.diamond_db: "$DB_ROOT/diamond/uniref90.dmnd"`.

### 2.7 CARD / RGI (`database/arg/card`)

```bash
mkdir -p "$DB_ROOT/arg/card" && cd "$DB_ROOT/arg/card"
# Download “CARD data” JSON package from https://card.mcmaster.ca/download and extract
# rgi load --card_json /path/to/card.json --local
# Or: rgi auto_load  (follow RGI version docs)
```

When `pipeline.enable_arg: true`, the Agent uses RGI/DeepARG; DBs must be on container-accessible paths.

### 2.8 VFDB (`database/virulence/vfdb`)

```bash
mkdir -p "$DB_ROOT/virulence/vfdb" && cd "$DB_ROOT/virulence/vfdb"
# Download protein sequences from http://www.mgc.ac.cn/VFs/download.htm
# diamond makedb --in VFDB_setA_pro.fas --db vfdb
```

Optional: point custom config at `vfdb.dmnd` or mount it on the functional annotation volume.

### 2.9 HUMAnN (optional, `database/humann`)

```bash
mkdir -p "$DB_ROOT/humann"
humann_databases --download chocophlan full "$DB_ROOT/humann"
humann_databases --download uniref uniref90_diamond "$DB_ROOT/humann"
# Configure HUMAnN env vars or wrappers to the directories above
```

### 2.10 RAG / KG (no need to download full DBs)

The interpretation layer defaults to the in-package curated index. To replace with full authority DBs for RAG:

1. Export JSON matching the `curated_bio_index.json` schema; or  
2. Use full DB paths for tools only, and keep RAG on the stub + PubMed.

---

## 3. Integrate with the Agent

```bash
# 1) Write site config
cp config/linux_server_gt256gb.yaml config/site.yaml
# Edit paths.* to absolute paths

# 2) Smoke (small data)
meta-agent run -i tests/fixtures/fastq -o /tmp/db_smoke \
  -m apptainer -c config/site.yaml --yes \
  -q "gut taxonomy smoke"

# 3) HITL: non-mock with missing paths triggers confirm_databases
#    Keep hitl.require_database_confirm: true (default)
```

Apptainer must be able to bind the DB directories, for example:

```bash
# Tools mount path parents via volumes; ensure DB_ROOT is readable on compute nodes
ls "$DB_ROOT/kraken_db/hash.k2d"
```

---

## 4. Validation checklist

```bash
# Host
ls ${paths_host_index}.1.bt2 2>/dev/null || ls ${paths_host_index}.1.bt2l

# Kraken2
test -f "$DB_ROOT/kraken_db/hash.k2d" && echo OK_kraken

# MetaPhlAn
ls "$DB_ROOT/metaphlan_db"/*.pkl 2>/dev/null | head

# GTDB-Tk
test -d "$DB_ROOT/gtdb" && echo OK_gtdb

# DIAMOND
test -f "$DB_ROOT/diamond/"*.dmnd && echo OK_diamond
```

---

## 5. Common issues

| Symptom | Remedy |
|---------|--------|
| HITL stuck on database confirm | Complete `paths.*` or temporarily set `require_database_confirm: false` |
| Kraken extremely slow | Place DB on local NVMe/scratch; avoid cross-site NFS |
| GTDB-Tk cannot find data | `export GTDBTK_DATA_PATH=...` matching `paths.gtdb` |
| RGI no hits | CARD not loaded via `rgi load`; check card.json |
| Disk full | Start with Standard Kraken + GTDB; install DIAMOND/HUMAnN later |
| ARM hosts | Most BioContainers are amd64; use `platform: linux/amd64` or x86 nodes |

---

## 6. Cross-references

- Usage: [docs/USAGE.md](../docs/USAGE.md)  
- Architecture: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)  
- Large-memory deployment: [docs/DEPLOY_LINUX.md](../docs/DEPLOY_LINUX.md)
