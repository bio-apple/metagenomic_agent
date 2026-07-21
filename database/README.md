# 参考数据库：目录契约与构建指南

本仓库 `database/` 存放**全量参考库**（或符号链接）。  
包内 RAG stub（`src/metagenomic_agent/rag/data/curated_bio_index.json`）仅用于解释/抗幻觉检索，**不能替代** Kraken2 / GTDB-Tk 等运行时库。

| 模式 | 是否需要本目录 |
|------|----------------|
| `mock` | 否 |
| `local` / `conda` / `docker` / `apptainer` | 是（至少 taxonomy + host；功能/ARG 按需） |

一键骨架脚本：[scripts/build_databases.sh](../scripts/build_databases.sh)（需自行准备网络与磁盘）。

---

## 1. 推荐布局与配置映射

在仓库根或 `/ref/databases` 建立：

```text
database/                         # 或 /ref/databases → 写进 config paths.*
├── host/
│   └── hg38/                     # Bowtie2 索引前缀：hg38
├── kraken_db/                    # Kraken2 标准库目录（含 hash.k2d 等）
├── metaphlan_db/                 # MetaPhlAn 数据库目录
├── gtdb/                         # GTDB-Tk release 数据根
├── eggnog/                       # eggNOG-mapper 数据
├── diamond/                      # DIAMOND .dmnd
├── humann/                       # chocophlan + uniref（可选）
├── arg/
│   ├── card/                     # CARD JSON（RGI load）
│   └── deeparg/                  # DeepARG 模型（可选）
├── virulence/
│   └── vfdb/                     # VFDB 蛋白/核酸（可选 DIAMOND）
├── taxonomy/                     # 可选：NCBI taxdump / GTDB 元数据镜像
├── function/                     # 可选：KEGG 本地镜像说明
├── pathway/                      # 可选：HUMAnN pathway
├── microbiome/                   # 可选：UHGG 等索引
└── literature/                   # 可选：本地 PMID JSON 缓存
```

在 `config/default.yaml` 或 `config/site.yaml`：

```yaml
paths:
  host_index: "/ref/databases/host/hg38"          # Bowtie2 前缀，无 .1.bt2 后缀
  kraken2_db: "/ref/databases/kraken_db"
  metaphlan_db: "/ref/databases/metaphlan_db"
  gtdb: "/ref/databases/gtdb"
  eggnog: "/ref/databases/eggnog"
  diamond_db: "/ref/databases/diamond/nr.dmnd"  # 或 uniref90.dmnd
```

相对路径相对于**运行 cwd**；生产请用**绝对路径**。

磁盘粗算（SSD/并行文件系统，勿放慢 NFS 热路径）：

| 库 | 约占用 |
|----|--------|
| 宿主 hg38 Bowtie2 | ~4–8 GB |
| Kraken2 Standard | ~50–100 GB+（随版本） |
| MetaPhlAn | ~5–15 GB |
| GTDB-Tk r214+ | ~50–80 GB |
| eggNOG | ~50 GB+ |
| DIAMOND UniRef | 视库 20–200 GB |
| CARD | <1 GB |

---

## 2. 构建步骤（按优先级）

以下命令在 Linux x86_64、已装对应工具或 BioContainers 下执行。  
`DB_ROOT` 示例：`export DB_ROOT=/ref/databases` 或 `$(pwd)/database`。

### 2.1 宿主去污染索引（`paths.host_index`）— **强烈建议**

```bash
export DB_ROOT=/ref/databases
mkdir -p "$DB_ROOT/host" && cd "$DB_ROOT/host"

# 下载人类参考（示例 GRCh38 主染色体；按单位规范替换）
# wget -O hg38.fa.gz "https://..."
# gunzip -c hg38.fa.gz > hg38.fa

# Bowtie2 建索引（前缀 = paths.host_index）
bowtie2-build --threads 16 hg38.fa hg38
# 产物：hg38.1.bt2 … → paths.host_index: "$DB_ROOT/host/hg38"
```

容器示例：

```bash
apptainer exec docker://quay.io/biocontainers/bowtie2:2.5.3--py39hd2f008b_0 \
  bowtie2-build --threads 16 hg38.fa hg38
```

### 2.2 Kraken2（`paths.kraken2_db`）— **分类必备**

**方式 A：下载官方预构建 Standard（推荐）**

```bash
mkdir -p "$DB_ROOT/kraken_db" && cd "$DB_ROOT/kraken_db"
# 查看当前镜像站 / 版本：https://benlangmead.github.io/aws-indexes/k2
# 示例（URL 随发布变更，以官网为准）：
# wget https://genome-idx.s3.amazonaws.com/kraken/k2_standard_YYYYMMDD.tar.gz
# tar -xzf k2_standard_*.tar.gz -C "$DB_ROOT/kraken_db"
# 解压后目录内应有：hash.k2d  opts.k2d  taxo.k2d
```

**方式 B：自行 `kraken2-build`**

```bash
DB="$DB_ROOT/kraken_db"
mkdir -p "$DB"
kraken2-build --download-taxonomy --db "$DB"
kraken2-build --download-library bacteria --db "$DB"   # 可加 archaea/viral/human
kraken2-build --download-library archaea --db "$DB"
# 人类读段若走 host 过滤，可不把 human 打进库
kraken2-build --build --db "$DB" --threads 32
# 可选：bracken-build -d "$DB" -t 32 -k 35 -l 150
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
# 安装 metaphlan 后：
metaphlan --install --bowtie2db "$DB_ROOT/metaphlan_db"
# 或指定版本索引（随 MetaPhlAn 文档）：
# metaphlan --install --index mpa_vOct22_CHOCOPhlAnSGB_202212 --bowtie2db "$DB_ROOT/metaphlan_db"
```

配置：`paths.metaphlan_db: "$DB_ROOT/metaphlan_db"`。

### 2.4 GTDB-Tk（`paths.gtdb`）— **MAG 分类**

```bash
mkdir -p "$DB_ROOT/gtdb" && cd "$DB_ROOT/gtdb"
# 按 https://ecogenomics.github.io/GTDBTk/installing/index.html
# 下载对应 release 的 gtdbtk_data.tar.gz（体积大）
# tar -xzf gtdbtk_rXXXvX_data.tar.gz -C "$DB_ROOT/gtdb"
# 解压后通常含：taxonomy/  markers/  masks/  metadata/ …

export GTDBTK_DATA_PATH="$DB_ROOT/gtdb"   # 或指向含 release 的子目录
```

配置：`paths.gtdb: "$DB_ROOT/gtdb"`（与 `GTDBTK_DATA_PATH` 一致）。

### 2.5 eggNOG（`paths.eggnog`）— **功能注释**

```bash
mkdir -p "$DB_ROOT/eggnog" && cd "$DB_ROOT/eggnog"
# 使用 eggnog-mapper 自带下载（需 eggnog-mapper 已安装）：
download_eggnog_data.py -y --data_dir "$DB_ROOT/eggnog"
# 或按 http://eggnog5.embl.de 文档拉取 diamond DB + annotations
```

配置：`paths.eggnog: "$DB_ROOT/eggnog"`。

### 2.6 DIAMOND（`paths.diamond_db`）

```bash
mkdir -p "$DB_ROOT/diamond" && cd "$DB_ROOT/diamond"
# 示例：UniRef90 FASTA → dmnd
# wget .../uniref90.fasta.gz && gunzip -c uniref90.fasta.gz > uniref90.fa
diamond makedb --in uniref90.fa --db uniref90 --threads 32
# 产物：uniref90.dmnd
```

配置：`paths.diamond_db: "$DB_ROOT/diamond/uniref90.dmnd"`。

### 2.7 CARD / RGI（`database/arg/card`）

```bash
mkdir -p "$DB_ROOT/arg/card" && cd "$DB_ROOT/arg/card"
# 从 https://card.mcmaster.ca/download 下载「CARD data」JSON 包并解压
# rgi load --card_json /path/to/card.json --local
# 或：rgi auto_load  （按 RGI 版本文档）
```

Agent 在 `pipeline.enable_arg: true` 时走 RGI/DeepARG；库需在容器可访问路径。

### 2.8 VFDB（`database/virulence/vfdb`）

```bash
mkdir -p "$DB_ROOT/virulence/vfdb" && cd "$DB_ROOT/virulence/vfdb"
# 从 http://www.mgc.ac.cn/VFs/download.htm 下载蛋白序列
# diamond makedb --in VFDB_setA_pro.fas --db vfdb
```

可选：将 `vfdb.dmnd` 写入自定义 config 或挂到功能注释卷。

### 2.9 HUMAnN（可选，`database/humann`）

```bash
mkdir -p "$DB_ROOT/humann"
humann_databases --download chocophlan full "$DB_ROOT/humann"
humann_databases --download uniref uniref90_diamond "$DB_ROOT/humann"
# 配置 HUMAnN 环境变量或 wrapper 指向上述目录
```

### 2.10 RAG / KG（无需下载全库）

解释层默认使用包内 curated 索引。若要替换全量权威库用于 RAG：

1. 导出与 `curated_bio_index.json` 同 schema 的 JSON；或  
2. 将全库路径仅用于工具，RAG 仍用 stub + PubMed。

---

## 3. 与 Agent 联调

```bash
# 1) 写 site 配置
cp config/linux_server_gt256gb.yaml config/site.yaml
# 编辑 paths.* 为绝对路径

# 2) 冒烟（小数据）
meta-agent run -i tests/fixtures/fastq -o /tmp/db_smoke \
  -m apptainer -c config/site.yaml --yes \
  -q "gut taxonomy smoke"

# 3) HITL：非 mock 且路径缺失会触发 confirm_databases
#    设 hitl.require_database_confirm: true（默认）
```

Apptainer 需能 bind 库目录，例如：

```bash
# 工具内部通过 volumes 挂载 paths 父目录；确保 DB_ROOT 对作业节点可读
ls "$DB_ROOT/kraken_db/hash.k2d"
```

---

## 4. 校验清单

```bash
# 宿主
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

| 现象 | 处理 |
|------|------|
| HITL 卡在数据库确认 | 补全 `paths.*` 或临时 `require_database_confirm: false` |
| Kraken 极慢 | 库放到本地 NVMe/scratch，勿用跨机房 NFS |
| GTDB-Tk 找不到数据 | `export GTDBTK_DATA_PATH=...` 与 `paths.gtdb` 一致 |
| RGI 无命中 | 未 `rgi load` CARD；检查 card.json |
| 磁盘打满 | Standard Kraken + GTDB 即可起步；DIAMOND/HUMAnN 后装 |
| ARM 机器 | BioContainers 多为 amd64；用 `platform: linux/amd64` 或 x86 节点 |

---

## 6. 与文档交叉引用

- 用法：[docs/USAGE.md](../docs/USAGE.md)  
- 架构：[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)  
- 大内存部署：[docs/DEPLOY_LINUX.md](../docs/DEPLOY_LINUX.md)
