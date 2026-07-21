> English: [DEPLOY_LINUX.md](DEPLOY_LINUX.md)

# Linux 大内存服务器部署指南（RAM ≥ 256 GB）

适用于在**≥256 GB** RAM 的单节点或 HPC 登录/计算节点上生产运行 Metagenomic Research Agent（v0.20+）。默认 `linux.max_memory_gb: 256` 会限制资源；大内存机器**必须**通过下方叠加配置抬高此上限。

配套文件：[config/linux_server_gt256gb.yaml](../config/linux_server_gt256gb.yaml)

## 1. 目标拓扑


| Component | Recommendation |
| --------- | -------------- |
| OS | Ubuntu 22.04+/RHEL 8+，x86_64 |
| Memory | ≥256 GB（组装/分箱推荐 512 GB+） |
| CPU | ≥32 物理核；配置线程 ≤ `nproc - 4` |
| Disk | 数据盘 ≥4 TB NVMe/并行文件系统；库与结果分盘 |
| Containers | **Apptainer**（HPC）或 Docker（有 root 的单节点） |
| Scheduler | 单节点 `local`；集群 `slurm` / `pbs` / `sge` |
| Python | 3.10–3.12，独立 venv |


```
/data/raw/fastq          # read-only raw data
/data/meta/samples.tsv   # metadata
/ref/databases/          # Kraken2 / GTDB / MetaPhlAn / host index
/scratch/$USER/          # fast work area + SIF cache
/results/$PROJECT/       # final products (optional backup to object storage)
```

## 2. 系统准备

```bash
# Confirm resources
free -h
nproc
df -h /data /scratch /ref 2>/dev/null || df -h

# Base packages (Debian/Ubuntu example)
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv git curl pigz

# Apptainer (prefer on HPC; without root use admin-provided modules)
# module load apptainer
apptainer --version || singularity --version

# Optional: Docker on a single node
# docker version
```

推荐内核/IO 设置：

- `vm.swappiness=10`（避免大作业在 swap 上颠簸）
- 工作目录放在本地 NVMe 或 Lustre/GPFS scratch；**不要**从慢 NFS 跑 Kraken 热路径
- 大库可暂存至 `/dev/shm`（见 `linux.prefer_shm`）；≥256 GB 节点可为 Kraken2 预留 80–120 GB shm，但勿撑满

```bash
# Example: expand shm to 120G (may not survive reboot; follow site fstab policy)
# sudo mount -o remount,size=120G /dev/shm
```

## 3. 如何部署软件栈（两层）

**不要**把 Kraken2/MEGAHIT 装进 Agent 的 Python 环境。使用两层：


| Layer | What to install | Recommended approach |
| ----- | --------------- | -------------------- |
| **A. Orchestration** | `meta-agent`、LangGraph、FastAPI… | Python **venv + pip** |
| **B. Bioinformatics tools** | fastp、Kraken2、MEGAHIT、CheckM2… | **Apptainer/Docker（BioContainers）** |


```
venv (meta-agent) ──schedules──► BioContainers tools in Apptainer/Docker
                               └── bind-mount /data, /ref, /results
```


| `mode` | Where tools come from | Suitable for |
| ------ | --------------------- | ------------ |
| `mock` | 无真实工具 | CI / smoke |
| `apptainer` | SIF（HPC 推荐） | 无 Docker root 的服务器 |
| `docker` | BioContainers 镜像 | 有 Docker 的单节点 |
| `conda` | 宿主 conda 环境 | 已有 bioconda 环境 |
| `local` | 宿主 PATH 二进制 | 生产不推荐 |


生产大内存主机：**A = venv，B = `apptainer`（或 `docker`）**。

### 3.1 层 A：安装 Agent（venv）

```bash
# System dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev \
  git curl pigz build-essential

# Optional: cluster module
# module load python/3.11

git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e ".[dev]"          # omit [dev] in production if preferred
# For Celery async queue: pip install -e ".[async]"

meta-agent version               # ≥ 0.20.0
pytest -q                        # optional smoke
```

每次登录：

```bash
cd /path/to/metagenomic_agent
source .venv/bin/activate
```

LLM（可选；mock / 本地 RAG 可不需要）：

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.deepseek.com/v1   # or on-prem vLLM
export OPENAI_MODEL=deepseek-chat
# Air-gapped: set literature.online: false in config
```

### 3.2 层 B（推荐）：Apptainer + BioContainers

```bash
# Confirm runtime
apptainer --version || singularity --version
# Without permissions: module load apptainer

# Place SIF cache on large disk (not home)
export APPTAINER_CACHEDIR=/scratch/$USER/containers
export SINGULARITY_CACHEDIR=$APPTAINER_CACHEDIR
mkdir -p "$APPTAINER_CACHEDIR"
# Also set apptainer.sif_dir in config/site.yaml
```

首次运行按需拉取；也可预拉常用镜像（钉扎在 `tools/context.py` → `DEFAULT_IMAGES`）：

```bash
SIF=$APPTAINER_CACHEDIR
apptainer pull "$SIF/fastp.sif"      docker://quay.io/biocontainers/fastp:0.23.4--h5f740d0_0
apptainer pull "$SIF/kraken2.sif"    docker://quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0
apptainer pull "$SIF/megahit.sif"    docker://quay.io/biocontainers/megahit:1.2.9--h43eeafb_4
apptainer pull "$SIF/metaphlan.sif"  docker://quay.io/biocontainers/metaphlan:4.1.0--pyhca03a8a_0
apptainer pull "$SIF/checkm2.sif"    docker://quay.io/biocontainers/checkm2:1.0.2--pyh7cba7a3_0
# Pull as needed: spades / metabat2 / gtdbtk / humann …
```

运行分析：

```bash
meta-agent run -i /data/fastq -o /results/run1 -m apptainer \
  -c config/linux_server_gt256gb.yaml --metadata /data/meta.tsv \
  -q "cohort shotgun analysis"
```

**Docker 单节点**（有 root / docker 组）：

```bash
sudo usermod -aG docker $USER   # re-login to take effect
docker pull quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0
# …
meta-agent run … -m docker -c config/site.yaml
```

### 3.3 层 B（备选）：Conda / Bioconda

仅当集群已集中维护 bioconda，或禁止容器时使用。

```bash
# Example: Miniforge
curl -L https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o mf.sh
bash mf.sh -b -p $HOME/miniforge3
source $HOME/miniforge3/etc/profile.d/conda.sh

conda create -y -n metagenomics -c bioconda -c conda-forge \
  fastp bowtie2 megahit metaphlan metabat2 checkm2 diamond
conda create -y -n kraken2_env -c bioconda -c conda-forge kraken2 bracken
conda create -y -n gtdbtk -c bioconda -c conda-forge gtdbtk

# Align names with config linux.conda_envs (defaults already match)
meta-agent run … -m conda -c config/site.yaml
```

`config/default.yaml`：

```yaml
linux:
  conda_envs:
    kraken2: kraken2_env
    gtdbtk: gtdbtk
    metagenomics: metagenomics
```

### 3.4 一键自检

```bash
source .venv/bin/activate
meta-agent version
python -c "from metagenomic_agent.tools.context import DEFAULT_IMAGES; print(len(DEFAULT_IMAGES), 'images pinned')"
apptainer --version || docker version || echo "WARN: no container runtime"
# Orchestration smoke (no reference DBs required)
meta-agent run -i tests/fixtures/fastq -o /tmp/meta-smoke --mode mock --yes \
  -q "smoke test"
```

## 4. 落地参考数据库

**按 [database/README.md](../database/README.md) 构建**；不要只建空目录。摘要：

```bash
export DB_ROOT=/ref/databases
bash scripts/build_databases.sh --layout
# Host: bash scripts/build_databases.sh --host /path/to/hg38.fa
# Kraken: set KRAKEN_TARBALL_URL then --kraken-download
# MetaPhlAn: bash scripts/build_databases.sh --metaphlan
# GTDB / eggNOG / DIAMOND / CARD: see database/README.md §2.4–2.8
bash scripts/build_databases.sh --check
# Merge $DB_ROOT/PATHS.example.yaml into config/site.yaml → paths.*
```

| Config key | Suggested absolute path | Notes |
|------------|-------------------------|-------|
| `paths.kraken2_db` | `/ref/databases/kraken_db` | 标准库约数十 GB；大库放最快盘 |
| `paths.gtdb` | `/ref/databases/gtdb` | GTDB-Tk 数据 |
| `paths.metaphlan_db` | `/ref/databases/metaphlan_db` | |
| `paths.host_index` | `/ref/databases/host/hg38` | Bowtie2 前缀 |
| `paths.eggnog` | `/ref/databases/eggnog` | 功能注释 |

数据库路径必须存在且可 bind-mount（Apptainer `--bind` / Docker `-v`）。  
投产前保持 HITL 数据库门控：`hitl.require_database_confirm: true`（非 mock 且路径缺失时停止）。

## 5. 大内存叠加配置

复制并按站点调整路径：

```bash
cp config/linux_server_gt256gb.yaml config/site.yaml
# Edit paths.*, slurm_*, apptainer.sif_dir
```

要点（已在 `linux_server_gt256gb.yaml` 中）：


| Key | ≥256 GB node suggestion | Why |
| --- | ----------------------- | --- |
| `mode` | `apptainer` 或 `docker` | 可重复；减少宿主依赖陷阱 |
| `linux.memory_gb` | 240–400 | 每作业声明内存（留 OS/缓存余量） |
| `linux.max_memory_gb` | **≥ 物理 RAM − 32** | 否则 cluster sense 会封顶 256 |
| `linux.threads` / `max_threads` | 32–64 / ≤ nproc−4 | 并行组装与分类 |
| `linux.prefer_shm` | `true` | 更快的库热读 |
| `pipeline.enable_assembly` | 按需 `true` | 大内存适合 metaSPAdes |
| `sandbox.prefer_container` | `true` | |
| `apptainer.sif_dir` | `/scratch/$USER/containers` | 避免撑爆 home 配额 |
| `hitl.auto_confirm` | 交互 `false`；批处理 `true` | 生产中确认关键步骤 |
| `hitl.mode` | 批处理 `sync`+`--yes`；服务 `async` | |


## 6. 如何运行

### 6.1 交互 / 登录节点试跑

```bash
source .venv/bin/activate
meta-agent run \
  -i /data/raw/fastq \
  -o /results/pilot \
  -m apptainer \
  -c config/site.yaml \
  --metadata /data/meta/samples.tsv \
  -q "IBD vs healthy shotgun biomarker discovery"
# Do not add --yes when confirming production gates; add -y for CI/nightly
```

### 6.2 SLURM 批作业

Agent 会写出 `executor/submit.slurm`（资源受 cluster sense 限制）。也可手写：

```bash
#!/bin/bash
#SBATCH --job-name=meta-agent
#SBATCH --partition=normal
#SBATCH --cpus-per-task=48
#SBATCH --mem=360G
#SBATCH --time=48:00:00
#SBATCH --output=/results/logs/%x-%j.out

set -euo pipefail
module load apptainer   # per site
source /path/to/metagenomic_agent/.venv/bin/activate
export APPTAINER_CACHEDIR=/scratch/$USER/containers
export SINGULARITY_CACHEDIR=$APPTAINER_CACHEDIR

meta-agent run \
  -i /data/raw/fastq -o /results/$SLURM_JOB_ID \
  -m apptainer -c config/site.yaml --yes \
  --metadata /data/meta/samples.tsv \
  -q "cohort shotgun analysis"
```

在 `config/site.yaml` 中：

```yaml
linux:
  scheduler: slurm
  slurm: true
  slurm_queue: normal
  slurm_account: YOUR_ACCOUNT
  slurm_time: "48:00:00"
```

### 6.3 API + 异步 HITL（Web 审批）

适合常开网关节点（勿在计算节点无头跑交互 Prompt）：

```bash
# systemd or screen/tmux
meta-agent serve --host 0.0.0.0 --port 8000

curl -X POST http://SERVER:8000/analyze -H 'Content-Type: application/json' -d '{
  "input_path": "/data/raw/fastq",
  "outdir": "/results/run1",
  "mode": "apptainer",
  "config_path": "config/site.yaml",
  "metadata_path": "/data/meta/samples.tsv",
  "hitl_mode": "async",
  "query": "IBD biomarker discovery"
}'
# Approve: GET/POST /runs/{run_id}/hitl?outdir=/results/run1
```

仅在内网开放防火墙；前置反向代理与鉴权。

## 7. 资源启发式（RAM ≥ 256 GB）


| Stage | Threads | Memory scale | Notes |
| ----- | ------- | ------------ | ----- |
| QC / host filter | 8–16 | 16–64 GB | |
| Kraken2 standard DB | 16–32 | 80–120 GB | 更大库需更多；优先本地盘/shm |
| MEGAHIT | 24–48 | 64–200 GB | 默认组装器 |
| metaSPAdes | 32–48 | **≥250 GB** | 仅在大内存机器启用 |
| MetaBAT2 / CheckM2 | 16–32 | 64–128 GB | |
| HUMAnN3 | 16–32 | 64–128 GB | 按需启用 `enable_humann` |


经验法则：**声明内存 = 峰值 × 1.1，且 ≤ 物理 RAM − 32 GB**；多作业队列策略下再进一步削减。

## 8. 生产检查清单

1. `free -h` ≥ 256 GB；已抬高 `linux.max_memory_gb`
2. 绝对路径 `paths.*` 存在；非 mock 运行通过数据库门控
3. Apptainer/Docker 可拉 BioContainers；`sif_dir` 在 scratch
4. 元数据含 `sample_id` + `group`
5. 先用小队列（2–4 样本）验证再扩规模
6. 启用 `cache.enabled` / `cache.per_sample_assembly` 以支持 checkpoint 续跑
7. 关键步骤：交互 → 关闭 `auto_confirm`；批处理 → `--yes`；远程 → `hitl_mode=async`
8. 发布前确认 `confirm_report_publish`（可分享 vs 内部草稿）
9. 备份 `/results/*/reproducibility/` 与 `workflow/params.yaml`

## 9. 故障排查


| Symptom | Remedy |
| ------- | ------ |
| 内存封顶在 256 GB | 抬高 `linux.max_memory_gb` 后重跑 |
| OOM / exit 137 | 降低 `threads`；组装改 MEGAHIT；检查同节点争用 |
| Apptainer 找不到库 | Bind 绝对路径；检查 SELinux/AppArmor |
| Home 目录满 | 将 `APPTAINER_CACHEDIR` 指到 scratch |
| 无 TTY 时 HITL 卡住 | `--yes` 或 API `async` |
| 文献 API 超时 | `literature.online: false` |
| Kraken 在 NFS 上极慢 | 将库拷到本地/scratch 或 shm |


更多 CLI/输出细节：[USAGE.zh-CN.md](USAGE.zh-CN.md)。
