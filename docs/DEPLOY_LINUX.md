# Linux 大内存服务器部署指南（RAM ≥ 256 GB）

面向单机或 HPC 登录/计算节点：内存 **≥256 GB**，运行 Metagenomic Research Agent（v0.20+）生产分析。默认配置 `linux.max_memory_gb: 256` 会封顶资源，大内存机必须用下文覆盖配置抬高上限。

配套文件：[config/linux_server_gt256gb.yaml](../config/linux_server_gt256gb.yaml)

## 1. 目标拓扑

| 组件 | 推荐 |
|------|------|
| OS | Ubuntu 22.04+/RHEL 8+，x86_64 |
| 内存 | ≥256 GB（建议 512 GB+ 做组装/binning） |
| CPU | ≥32 物理核；配置线程不超过 `nproc - 4` |
| 磁盘 | 数据盘 ≥4 TB NVMe/并行文件系统；库与结果分盘 |
| 容器 | **Apptainer**（HPC）或 Docker（单机 root） |
| 调度 | 单机 `local`；集群 `slurm` / `pbs` / `sge` |
| Python | 3.10–3.12，独立 venv |

```
/data/raw/fastq          # 只读原始数据
/data/meta/samples.tsv   # 元数据
/ref/databases/          # Kraken2 / GTDB / MetaPhlAn / host index
/scratch/$USER/          # 高速工作区 + SIF 缓存
/results/$PROJECT/       # 最终产物（可备份到对象存储）
```

## 2. 系统准备

```bash
# 资源确认
free -h
nproc
df -h /data /scratch /ref 2>/dev/null || df -h

# 基础包（Debian/Ubuntu 示例）
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv git curl pigz

# Apptainer（HPC 优先；无 root 时用管理员预装模块）
# module load apptainer
apptainer --version || singularity --version

# 可选：Docker 单机
# docker version
```

建议内核/IO：

- `vm.swappiness=10`（避免大作业被 swap 拖死）
- 工作目录放本地 NVMe 或 Lustre/GPFS scratch，**不要**把 Kraken 库放在慢 NFS 上跑热路径
- 大库可挂到 `/dev/shm`（见 `linux.prefer_shm`）；≥256 GB 机可给 Kraken2 留 80–120 GB shm，勿占满

```bash
# 示例：给 shm 扩到 120G（重启可能失效，按站点策略改 fstab）
# sudo mount -o remount,size=120G /dev/shm
```

## 3. 软件环境怎么部署（两层）

本项目**不要**把 Kraken2/MEGAHIT 等装进 Agent 的 Python 环境。环境分两层：

| 层 | 装什么 | 推荐方式 |
|----|--------|----------|
| **A. 编排层** | `meta-agent`、LangGraph、FastAPI… | Python **venv + pip** |
| **B. 生信工具层** | fastp、Kraken2、MEGAHIT、CheckM2… | **Apptainer/Docker（BioContainers）** |

```
venv (meta-agent) ──调度──► Apptainer/Docker 里的 biocontainers 工具
                         └── bind 挂载 /data、/ref、/results
```

| `mode` | 工具从哪来 | 适用 |
|--------|------------|------|
| `mock` | 不跑真工具 | CI / 冒烟 |
| `apptainer` | SIF（推荐 HPC） | 无 Docker root 的服务器 |
| `docker` | BioContainers 镜像 | 单机有 Docker |
| `conda` | 主机 conda env | 已有 bioconda 环境时 |
| `local` | 主机 PATH 二进制 | 不推荐生产 |

生产大内存机：**A 用 venv，B 用 `apptainer`（或 `docker`）**。

### 3.1 层 A：安装 Agent（venv）

```bash
# 系统依赖（Ubuntu/Debian）
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev \
  git curl pigz build-essential

# 可选：集群已有 module
# module load python/3.11

git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e ".[dev]"          # 生产可不加 [dev]
# 若要用 Celery 异步队列：pip install -e ".[async]"

meta-agent version               # ≥ 0.20.0
pytest -q                        # 可选冒烟
```

每次登录：

```bash
cd /path/to/metagenomic_agent
source .venv/bin/activate
```

LLM（可选，不配也能跑 mock / 本地 RAG）：

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或机房 vLLM
export OPENAI_MODEL=deepseek-chat
# 空气墙：config 里 literature.online: false
```

### 3.2 层 B（推荐）：Apptainer + BioContainers

```bash
# 确认运行时
apptainer --version || singularity --version
# 无权限时：module load apptainer

# SIF 缓存放到大盘（勿用家目录）
export APPTAINER_CACHEDIR=/scratch/$USER/containers
export SINGULARITY_CACHEDIR=$APPTAINER_CACHEDIR
mkdir -p "$APPTAINER_CACHEDIR"
# 同步写到 config/site.yaml → apptainer.sif_dir
```

首次会按需 pull；也可预拉常用镜像（镜像 pin 见 `tools/context.py` → `DEFAULT_IMAGES`）：

```bash
SIF=$APPTAINER_CACHEDIR
apptainer pull "$SIF/fastp.sif"      docker://quay.io/biocontainers/fastp:0.23.4--h5f740d0_0
apptainer pull "$SIF/kraken2.sif"    docker://quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0
apptainer pull "$SIF/megahit.sif"    docker://quay.io/biocontainers/megahit:1.2.9--h43eeafb_4
apptainer pull "$SIF/metaphlan.sif"  docker://quay.io/biocontainers/metaphlan:4.1.0--pyhca03a8a_0
apptainer pull "$SIF/checkm2.sif"    docker://quay.io/biocontainers/checkm2:1.0.2--pyh7cba7a3_0
# 需要时再拉：spades / metabat2 / gtdbtk / humann …
```

跑分析：

```bash
meta-agent run -i /data/fastq -o /results/run1 -m apptainer \
  -c config/linux_server_gt256gb.yaml --metadata /data/meta.tsv \
  -q "cohort shotgun analysis"
```

**Docker 单机**（有 root / 用户组权限时）：

```bash
sudo usermod -aG docker $USER   # 重新登录生效
docker pull quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0
# …
meta-agent run … -m docker -c config/site.yaml
```

### 3.3 层 B（备选）：Conda / Bioconda

仅在集群已统一维护 bioconda、或不允许容器时使用。

```bash
# 示例：Miniforge
curl -L https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o mf.sh
bash mf.sh -b -p $HOME/miniforge3
source $HOME/miniforge3/etc/profile.d/conda.sh

conda create -y -n metagenomics -c bioconda -c conda-forge \
  fastp bowtie2 megahit metaphlan metabat2 checkm2 diamond
conda create -y -n kraken2_env -c bioconda -c conda-forge kraken2 bracken
conda create -y -n gtdbtk -c bioconda -c conda-forge gtdbtk

# 与 config linux.conda_envs 名称对齐（默认已是这些名字）
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
# 编排层冒烟（不依赖参考库）
meta-agent run -i tests/fixtures/fastq -o /tmp/meta-smoke --mode mock --yes \
  -q "smoke test"
```

## 4. 参考库落地

库路径必须存在且可被容器 bind-mount（Apptainer `--bind` / Docker `-v`）。详见 [database/README.md](../database/README.md)。

| 配置键 | 建议绝对路径 | 备注 |
|--------|--------------|------|
| `paths.kraken2_db` | `/ref/databases/kraken2` | 标准库约数十 GB；大库放到最快盘 |
| `paths.gtdb` | `/ref/databases/gtdb` | GTDB-Tk 数据 |
| `paths.metaphlan_db` | `/ref/databases/metaphlan` | |
| `paths.host_index` | `/ref/databases/host/hg38` | Bowtie2 前缀 |
| `paths.eggnog` | `/ref/databases/eggnog` | 功能注释 |

生产前用 HITL 数据库门控确认：`hitl.require_database_confirm: true`（非 mock 且路径缺失会停）。

## 5. 大内存覆盖配置

复制并按站点改路径：

```bash
cp config/linux_server_gt256gb.yaml config/site.yaml
# 编辑 paths.*、slurm_*、apptainer.sif_dir
```

要点（已写在 `linux_server_gt256gb.yaml`）：

| 键 | ≥256 GB 机建议 | 原因 |
|----|----------------|------|
| `mode` | `apptainer` 或 `docker` | 可复现，少踩主机依赖 |
| `linux.memory_gb` | 240–400 | 单作业申报内存（留 OS/缓存） |
| `linux.max_memory_gb` | **≥ 物理内存 − 32** | 否则 cluster sense 封在 256 |
| `linux.threads` / `max_threads` | 32–64 / ≤ nproc−4 | 组装与分类并行 |
| `linux.prefer_shm` | `true` | 加速 DB 热读 |
| `pipeline.enable_assembly` | 按需 `true` | 大内存才适合 metaSPAdes |
| `sandbox.prefer_container` | `true` | |
| `apptainer.sif_dir` | `/scratch/$USER/containers` | 避免家目录配额打满 |
| `hitl.auto_confirm` | 交互 `false`；批处理 `true` | 生产关键步骤确认 |
| `hitl.mode` | 批处理 `sync`+`--yes`；服务 `async` | |

## 6. 运行方式

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
# 生产确认门控时不要加 --yes；CI/夜跑再加 -y
```

### 6.2 SLURM 批作业

Agent 会写出 `executor/submit.slurm`（资源经 cluster sense 封顶）。也可手写：

```bash
#!/bin/bash
#SBATCH --job-name=meta-agent
#SBATCH --partition=normal
#SBATCH --cpus-per-task=48
#SBATCH --mem=360G
#SBATCH --time=48:00:00
#SBATCH --output=/results/logs/%x-%j.out

set -euo pipefail
module load apptainer   # 按站点
source /path/to/metagenomic_agent/.venv/bin/activate
export APPTAINER_CACHEDIR=/scratch/$USER/containers
export SINGULARITY_CACHEDIR=$APPTAINER_CACHEDIR

meta-agent run \
  -i /data/raw/fastq -o /results/$SLURM_JOB_ID \
  -m apptainer -c config/site.yaml --yes \
  --metadata /data/meta/samples.tsv \
  -q "cohort shotgun analysis"
```

`config/site.yaml` 中设置：

```yaml
linux:
  scheduler: slurm
  slurm: true
  slurm_queue: normal
  slurm_account: YOUR_ACCOUNT
  slurm_time: "48:00:00"
```

### 6.3 API + 异步 HITL（Web 审批）

适合网关节点常驻服务（勿在超算计算节点无头跑交互 Prompt）：

```bash
# systemd 或 screen/tmux
meta-agent serve --host 0.0.0.0 --port 8000

curl -X POST http://服务器:8000/analyze -H 'Content-Type: application/json' -d '{
  "input_path": "/data/raw/fastq",
  "outdir": "/results/run1",
  "mode": "apptainer",
  "config_path": "config/site.yaml",
  "metadata_path": "/data/meta/samples.tsv",
  "hitl_mode": "async",
  "query": "IBD biomarker discovery"
}'
# 审批：GET/POST /runs/{run_id}/hitl?outdir=/results/run1
```

防火墙仅开放内网；前面加反向代理与鉴权。

## 7. 资源经验值（RAM ≥ 256 GB）

| 阶段 | 线程 | 内存量级 | 备注 |
|------|------|----------|------|
| QC / host filter | 8–16 | 16–64 GB | |
| Kraken2 标准库 | 16–32 | 80–120 GB | 大库可更高；优先本地盘/shm |
| MEGAHIT | 24–48 | 64–200 GB | 默认组装器 |
| metaSPAdes | 32–48 | **≥250 GB** | 仅大内存机开启 |
| MetaBAT2 / CheckM2 | 16–32 | 64–128 GB | |
| HUMAnN3 | 16–32 | 64–128 GB | `enable_humann` 按需 |

原则：**申报内存 = 峰值 × 1.1，且 ≤ 物理内存 − 32 GB**；多作业共节点时按队列策略再砍。

## 8. 生产检查清单

1. `free -h` ≥ 256 GB；`linux.max_memory_gb` 已抬高  
2. `paths.*` 绝对路径存在；非 mock 跑通数据库门控  
3. Apptainer/Docker 能 pull BioContainers；`sif_dir` 在 scratch  
4. 元数据含 `sample_id` + `group`  
5. 首次队列作业用小队列（2–4 样本）验证后扩队列  
6. 打开 `cache.enabled` / `cache.per_sample_assembly` 以便断点续跑  
7. 关键步骤：交互关 `auto_confirm`；批处理 `--yes`；远程用 `hitl_mode=async`  
8. 报告外发前确认 `confirm_report_publish`（可分享 vs 内部草稿）  
9. 备份 `/results/*/reproducibility/` 与 `workflow/params.yaml`

## 9. 排障

| 现象 | 处理 |
|------|------|
| 内存被封在 256 GB | 提高 `linux.max_memory_gb`，重跑 |
| OOM / exit 137 | 降 `threads`；组装改 MEGAHIT；检查同节点抢占 |
| Apptainer 找不到库 | bind 绝对路径；检查 SELinux/AppArmor |
| 家目录满 | `APPTAINER_CACHEDIR` 指到 scratch |
| HITL 卡住无 TTY | `--yes` 或 API `async` |
| 文献 API 超时 | `literature.online: false` |
| NFS 上 Kraken 极慢 | 库拷到本地/scratch 或 shm |

更细的 CLI/产物说明见 [USAGE.md](USAGE.md)。
