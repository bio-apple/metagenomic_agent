# Linux Large-Memory Server Deployment Guide (RAM ≥ 256 GB)

For single-node or HPC login/compute nodes with **≥256 GB** RAM running Metagenomic Research Agent (v0.20+) in production. The default `linux.max_memory_gb: 256` caps resources; large-memory machines **must** raise this ceiling via the overlay config below.

Companion file: [config/linux_server_gt256gb.yaml](../config/linux_server_gt256gb.yaml)

## 1. Target topology


| Component | Recommendation |
| --------- | -------------- |
| OS | Ubuntu 22.04+/RHEL 8+, x86_64 |
| Memory | ≥256 GB (512 GB+ recommended for assembly/binning) |
| CPU | ≥32 physical cores; configure threads ≤ `nproc - 4` |
| Disk | Data volume ≥4 TB NVMe/parallel FS; separate disks for DBs and results |
| Containers | **Apptainer** (HPC) or Docker (single-node with root) |
| Scheduler | Single-node `local`; cluster `slurm` / `pbs` / `sge` |
| Python | 3.10–3.12, dedicated venv |


```
/data/raw/fastq          # read-only raw data
/data/meta/samples.tsv   # metadata
/ref/databases/          # Kraken2 / GTDB / MetaPhlAn / host index
/scratch/$USER/          # fast work area + SIF cache
/results/$PROJECT/       # final products (optional backup to object storage)
```

## 2. System preparation

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

Recommended kernel/IO settings:

- `vm.swappiness=10` (avoid large jobs thrashing on swap)
- Place work directories on local NVMe or Lustre/GPFS scratch; **do not** run Kraken hot paths from slow NFS
- Large DBs may be staged under `/dev/shm` (see `linux.prefer_shm`); on ≥256 GB nodes reserve 80–120 GB shm for Kraken2 without filling it

```bash
# Example: expand shm to 120G (may not survive reboot; follow site fstab policy)
# sudo mount -o remount,size=120G /dev/shm
```

## 3. How to deploy the software stack (two layers)

**Do not** install Kraken2/MEGAHIT into the Agent Python environment. Use two layers:


| Layer | What to install | Recommended approach |
| ----- | --------------- | -------------------- |
| **A. Orchestration** | `meta-agent`, LangGraph, FastAPI… | Python **venv + pip** |
| **B. Bioinformatics tools** | fastp, Kraken2, MEGAHIT, CheckM2… | **Apptainer/Docker (BioContainers)** |


```
venv (meta-agent) ──schedules──► BioContainers tools in Apptainer/Docker
                               └── bind-mount /data, /ref, /results
```


| `mode` | Where tools come from | Suitable for |
| ------ | --------------------- | ------------ |
| `mock` | No real tools | CI / smoke |
| `apptainer` | SIF (recommended on HPC) | Servers without Docker root |
| `docker` | BioContainers images | Single node with Docker |
| `conda` | Host conda env | Existing bioconda environments |
| `local` | Host PATH binaries | Not recommended for production |


Production large-memory hosts: **A = venv, B = `apptainer` (or `docker`)**.

### 3.1 Layer A: install the Agent (venv)

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

On each login:

```bash
cd /path/to/metagenomic_agent
source .venv/bin/activate
```

LLM (optional; mock / local RAG work without it):

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.deepseek.com/v1   # or on-prem vLLM
export OPENAI_MODEL=deepseek-chat
# Air-gapped: set literature.online: false in config
```

### 3.2 Layer B (recommended): Apptainer + BioContainers

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

First runs pull on demand; you may also pre-pull common images (pins in `tools/context.py` → `DEFAULT_IMAGES`):

```bash
SIF=$APPTAINER_CACHEDIR
apptainer pull "$SIF/fastp.sif"      docker://quay.io/biocontainers/fastp:0.23.4--h5f740d0_0
apptainer pull "$SIF/kraken2.sif"    docker://quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0
apptainer pull "$SIF/megahit.sif"    docker://quay.io/biocontainers/megahit:1.2.9--h43eeafb_4
apptainer pull "$SIF/metaphlan.sif"  docker://quay.io/biocontainers/metaphlan:4.1.0--pyhca03a8a_0
apptainer pull "$SIF/checkm2.sif"    docker://quay.io/biocontainers/checkm2:1.0.2--pyh7cba7a3_0
# Pull as needed: spades / metabat2 / gtdbtk / humann …
```

Run analysis:

```bash
meta-agent run -i /data/fastq -o /results/run1 -m apptainer \
  -c config/linux_server_gt256gb.yaml --metadata /data/meta.tsv \
  -q "cohort shotgun analysis"
```

**Docker single-node** (with root / docker group):

```bash
sudo usermod -aG docker $USER   # re-login to take effect
docker pull quay.io/biocontainers/kraken2:2.1.3--pl5321hdcf5f25_0
# …
meta-agent run … -m docker -c config/site.yaml
```

### 3.3 Layer B (alternative): Conda / Bioconda

Use only when the cluster already maintains bioconda centrally, or containers are disallowed.

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

`config/default.yaml`:

```yaml
linux:
  conda_envs:
    kraken2: kraken2_env
    gtdbtk: gtdbtk
    metagenomics: metagenomics
```

### 3.4 One-shot self-check

```bash
source .venv/bin/activate
meta-agent version
python -c "from metagenomic_agent.tools.context import DEFAULT_IMAGES; print(len(DEFAULT_IMAGES), 'images pinned')"
apptainer --version || docker version || echo "WARN: no container runtime"
# Orchestration smoke (no reference DBs required)
meta-agent run -i tests/fixtures/fastq -o /tmp/meta-smoke --mode mock --yes \
  -q "smoke test"
```

## 4. Landing reference databases

**Build following [database/README.md](../database/README.md)**; do not create empty directories only. Summary:

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
| `paths.kraken2_db` | `/ref/databases/kraken_db` | Standard ~tens of GB; put large DBs on fastest disk |
| `paths.gtdb` | `/ref/databases/gtdb` | GTDB-Tk data |
| `paths.metaphlan_db` | `/ref/databases/metaphlan_db` | |
| `paths.host_index` | `/ref/databases/host/hg38` | Bowtie2 prefix |
| `paths.eggnog` | `/ref/databases/eggnog` | Functional annotation |

DB paths must exist and be bind-mountable (Apptainer `--bind` / Docker `-v`).  
Before production, keep the HITL database gate: `hitl.require_database_confirm: true` (stops when non-mock and paths are missing).

## 5. Large-memory overlay config

Copy and adjust paths for your site:

```bash
cp config/linux_server_gt256gb.yaml config/site.yaml
# Edit paths.*, slurm_*, apptainer.sif_dir
```

Key points (already in `linux_server_gt256gb.yaml`):


| Key | ≥256 GB node suggestion | Why |
| --- | ----------------------- | --- |
| `mode` | `apptainer` or `docker` | Reproducible; fewer host dependency traps |
| `linux.memory_gb` | 240–400 | Per-job declared memory (leave OS/cache headroom) |
| `linux.max_memory_gb` | **≥ physical RAM − 32** | Otherwise cluster sense caps at 256 |
| `linux.threads` / `max_threads` | 32–64 / ≤ nproc−4 | Parallel assembly and taxonomy |
| `linux.prefer_shm` | `true` | Faster DB hot reads |
| `pipeline.enable_assembly` | `true` as needed | Large RAM is suitable for metaSPAdes |
| `sandbox.prefer_container` | `true` | |
| `apptainer.sif_dir` | `/scratch/$USER/containers` | Avoid filling home quota |
| `hitl.auto_confirm` | Interactive `false`; batch `true` | Confirm critical steps in production |
| `hitl.mode` | Batch `sync`+`--yes`; service `async` | |


## 6. How to run

### 6.1 Interactive / login-node pilot

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

### 6.2 SLURM batch job

The Agent writes `executor/submit.slurm` (resources capped by cluster sense). You may also hand-write:

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

In `config/site.yaml`:

```yaml
linux:
  scheduler: slurm
  slurm: true
  slurm_queue: normal
  slurm_account: YOUR_ACCOUNT
  slurm_time: "48:00:00"
```

### 6.3 API + async HITL (Web approval)

Suitable for a always-on gateway node (do not run interactive Prompts headless on compute nodes):

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

Open the firewall only on the intranet; place a reverse proxy and auth in front.

## 7. Resource heuristics (RAM ≥ 256 GB)


| Stage | Threads | Memory scale | Notes |
| ----- | ------- | ------------ | ----- |
| QC / host filter | 8–16 | 16–64 GB | |
| Kraken2 standard DB | 16–32 | 80–120 GB | Larger DBs need more; prefer local disk/shm |
| MEGAHIT | 24–48 | 64–200 GB | Default assembler |
| metaSPAdes | 32–48 | **≥250 GB** | Enable only on large-memory machines |
| MetaBAT2 / CheckM2 | 16–32 | 64–128 GB | |
| HUMAnN3 | 16–32 | 64–128 GB | Enable `enable_humann` as needed |


Rule of thumb: **declared memory = peak × 1.1, and ≤ physical RAM − 32 GB**; cut further under multi-job queue policy.

## 8. Production checklist

1. `free -h` ≥ 256 GB; `linux.max_memory_gb` raised
2. Absolute `paths.*` exist; non-mock runs pass the database gate
3. Apptainer/Docker can pull BioContainers; `sif_dir` on scratch
4. Metadata includes `sample_id` + `group`
5. Validate with a small queue (2–4 samples) before scaling
6. Enable `cache.enabled` / `cache.per_sample_assembly` for checkpoint resume
7. Critical steps: interactive → disable `auto_confirm`; batch → `--yes`; remote → `hitl_mode=async`
8. Confirm `confirm_report_publish` before release (shareable vs internal draft)
9. Back up `/results/*/reproducibility/` and `workflow/params.yaml`

## 9. Troubleshooting


| Symptom | Remedy |
| ------- | ------ |
| Memory capped at 256 GB | Raise `linux.max_memory_gb` and re-run |
| OOM / exit 137 | Lower `threads`; switch assembly to MEGAHIT; check co-node contention |
| Apptainer cannot find DBs | Bind absolute paths; check SELinux/AppArmor |
| Home directory full | Point `APPTAINER_CACHEDIR` to scratch |
| HITL stuck without TTY | `--yes` or API `async` |
| Literature API timeout | `literature.online: false` |
| Kraken extremely slow on NFS | Copy DB to local/scratch or shm |


More CLI/output detail: [USAGE.md](USAGE.md).
