> English: [README.md](README.md)

# 参考数据库：目录约定与构建指南

仓库 `database/` 目录存放**完整参考数据库**（或符号链接）。  
包内 RAG 桩（`src/metagenomic_agent/rag/data/curated_bio_index.json`）仅用于解读 / 抗幻觉检索，**不能替代** Kraken2 / GTDB-Tk 等运行时库。

| Mode | Requires this directory? |
|------|--------------------------|
| `mock` | 否 |
| `local` / `conda` / `docker` / `apptainer` | 是（至少分类 + 宿主；功能/ARG 按需） |

骨架辅助脚本：[scripts/build_databases.sh](../scripts/build_databases.sh)（需自行提供网络与磁盘）。

---

## 1. 推荐布局与配置映射

在仓库根目录或 `/ref/databases` 下创建：

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

在 `config/default.yaml` 或 `config/site.yaml` 中：

```yaml
paths:
  host_index: "/ref/databases/host/hg38"          # Bowtie2 prefix, without .1.bt2 suffix
  kraken2_db: "/ref/databases/kraken_db"
  metaphlan_db: "/ref/databases/metaphlan_db"
  gtdb: "/ref/databases/gtdb"
  eggnog: "/ref/databases/eggnog"
  diamond_db: "/ref/databases/diamond/nr.dmnd"  # or uniref90.dmnd
```

相对路径相对**运行时 cwd** 解析；生产请使用**绝对路径**。

粗略磁盘估算（SSD/并行文件系统；热路径避免慢 NFS）：

| Database | Approx. size |
|----------|--------------|
| Host hg38 Bowtie2 | ~4–8 GB |
| Kraken2 Standard | ~50–100 GB+（视版本） |
| MetaPhlAn | ~5–15 GB |
| GTDB-Tk r214+ | ~50–80 GB |
| eggNOG | ~50 GB+ |
| DIAMOND UniRef | 20–200 GB（视库而定） |
| CARD | <1 GB |

---

## 2. 构建步骤（按优先级）

在已安装对应工具或 BioContainers 的 Linux x86_64 上运行。  
示例 `DB_ROOT`：`export DB_ROOT=/ref/databases` 或 `$(pwd)/database`。

### 2.1 宿主去污染索引（`paths.host_index`）——**强烈推荐**

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

容器示例：

```bash
apptainer exec docker://quay.io/biocontainers/bowtie2:2.5.3--py39hd2f008b_0 \
  bowtie2-build --threads 16 hg38.fa hg38
```

### 2.2 Kraken2（`paths.kraken2_db`）——**分类必需**

**选项 A：下载官方预构建 Standard（推荐）**

```bash
mkdir -p "$DB_ROOT/kraken_db" && cd "$DB_ROOT/kraken_db"
# Check current mirrors / versions: https://benlangmead.github.io/aws-indexes/k2
# Example (URL changes with releases; follow the official site):
# wget https://genome-idx.s3.amazonaws.com/kraken/k2_standard_YYYYMMDD.tar.gz
# tar -xzf k2_standard_*.tar.gz -C "$DB_ROOT/kraken_db"
# After extract the directory should contain: hash.k2d  opts.k2d  taxo.k2d
```

**选项 B：用 `kraken2-build` 构建**

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

校验：

```bash
ls "$DB_ROOT/kraken_db"/hash.k2d "$DB_ROOT/kraken_db"/taxo.k2d
kraken2 --db "$DB_ROOT/kraken_db" --threads 4 --paired R1.fq R2.fq --report /tmp/t.kreport >/dev/null
```

配置：`paths.kraken2_db: "$DB_ROOT/kraken_db"`。

### 2.3 MetaPhlAn（`paths.metaphlan_db`）

```bash
mkdir -p "$DB_ROOT/metaphlan_db"
# After installing metaphlan:
metaphlan --install --bowtie2db "$DB_ROOT/metaphlan_db"
# Or a versioned index (follow MetaPhlAn docs):
# metaphlan --install --index mpa_vOct22_CHOCOPhlAnSGB_202212 --bowtie2db "$DB_ROOT/metaphlan_db"
```

配置：`paths.metaphlan_db: "$DB_ROOT/metaphlan_db"`。

### 2.4 GTDB-Tk（`paths.gtdb`）——**MAG 分类**

```bash
mkdir -p "$DB_ROOT/gtdb" && cd "$DB_ROOT/gtdb"
# Follow https://ecogenomics.github.io/GTDBTk/installing/index.html
# Download the matching release gtdbtk_data.tar.gz (large)
# tar -xzf gtdbtk_rXXXvX_data.tar.gz -C "$DB_ROOT/gtdb"
# Extracted tree usually includes: taxonomy/  markers/  masks/  metadata/ …

export GTDBTK_DATA_PATH="$DB_ROOT/gtdb"   # or the release subdirectory
```

配置：`paths.gtdb: "$DB_ROOT/gtdb"`（须与 `GTDBTK_DATA_PATH` 一致）。

### 2.5 eggNOG（`paths.eggnog`）——**功能注释**

```bash
mkdir -p "$DB_ROOT/eggnog" && cd "$DB_ROOT/eggnog"
# Use eggnog-mapper's downloader (eggnog-mapper must be installed):
download_eggnog_data.py -y --data_dir "$DB_ROOT/eggnog"
# Or follow http://eggnog5.embl.de for diamond DB + annotations
```

配置：`paths.eggnog: "$DB_ROOT/eggnog"`。

### 2.6 DIAMOND（`paths.diamond_db`）

```bash
mkdir -p "$DB_ROOT/diamond" && cd "$DB_ROOT/diamond"
# Example: UniRef90 FASTA → dmnd
# wget .../uniref90.fasta.gz && gunzip -c uniref90.fasta.gz > uniref90.fa
diamond makedb --in uniref90.fa --db uniref90 --threads 32
# Product: uniref90.dmnd
```

配置：`paths.diamond_db: "$DB_ROOT/diamond/uniref90.dmnd"`。

### 2.7 CARD / RGI（`database/arg/card`）

```bash
mkdir -p "$DB_ROOT/arg/card" && cd "$DB_ROOT/arg/card"
# Download “CARD data” JSON package from https://card.mcmaster.ca/download and extract
# rgi load --card_json /path/to/card.json --local
# Or: rgi auto_load  (follow RGI version docs)
```

当 `pipeline.enable_arg: true` 时，Agent 使用 RGI/DeepARG；库须在容器可访问路径上。

### 2.8 VFDB（`database/virulence/vfdb`）

```bash
mkdir -p "$DB_ROOT/virulence/vfdb" && cd "$DB_ROOT/virulence/vfdb"
# Download protein sequences from http://www.mgc.ac.cn/VFs/download.htm
# diamond makedb --in VFDB_setA_pro.fas --db vfdb
```

可选：在自定义配置中指向 `vfdb.dmnd`，或挂载到功能注释卷。

### 2.9 HUMAnN（可选，`database/humann`）

```bash
mkdir -p "$DB_ROOT/humann"
humann_databases --download chocophlan full "$DB_ROOT/humann"
humann_databases --download uniref uniref90_diamond "$DB_ROOT/humann"
# Configure HUMAnN env vars or wrappers to the directories above
```

### 2.10 RAG / KG（无需下载完整库）

解读层默认使用包内 curated 索引。若要用完整权威库替换 RAG：

1. 导出符合 `curated_bio_index.json` schema 的 JSON；或  
2. 仅将完整库路径用于工具，RAG 仍用桩 + PubMed。

---

## 3. 与 Agent 集成

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

Apptainer 必须能 bind 数据库目录，例如：

```bash
# Tools mount path parents via volumes; ensure DB_ROOT is readable on compute nodes
ls "$DB_ROOT/kraken_db/hash.k2d"
```

---

## 4. 校验清单

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

## 5. 常见问题

| Symptom | Remedy |
|---------|--------|
| HITL 卡在数据库确认 | 补全 `paths.*`，或临时设 `require_database_confirm: false` |
| Kraken 极慢 | 将库放本地 NVMe/scratch；避免跨站 NFS |
| GTDB-Tk 找不到数据 | `export GTDBTK_DATA_PATH=...` 与 `paths.gtdb` 一致 |
| RGI 无命中 | 未通过 `rgi load` 加载 CARD；检查 card.json |
| 磁盘满 | 先装 Standard Kraken + GTDB；稍后装 DIAMOND/HUMAnN |
| ARM 主机 | 多数 BioContainers 为 amd64；用 `platform: linux/amd64` 或 x86 节点 |

---

## 6. 交叉引用

- 用法：[docs/USAGE.md](../docs/USAGE.md)  
- 架构：[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)  
- 大内存部署：[docs/DEPLOY_LINUX.md](../docs/DEPLOY_LINUX.md)
