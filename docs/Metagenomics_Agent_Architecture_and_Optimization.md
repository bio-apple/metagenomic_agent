# 宏基因组生信智能体（Metagenomics AI Agent）架构设计与部署优化方案

> **归档说明（v0.5）**：本文为 Linux 生产 / MAGs 优化方案草稿，部分节点命名已演进。  
> 当前实现请以 [ARCHITECTURE.md](ARCHITECTURE.md) 与 [METHODS.md](METHODS.md) 为准；顶刊三阶段落地见 [OPTIMIZATION_PROPOSAL_IMPL.md](OPTIMIZATION_PROPOSAL_IMPL.md)。

## 1. 概述

本方案旨在针对基于大语言模型（LLM）的**宏基因组生信智能体（Metagenomics AI Agent）**进行架构完善与工程化升级。针对从传统 Mac/单机环境迁移至 **Linux 生产级服务器环境** 的需求，提供从任务规划、容错闭环、多组学/MAGs工具链扩展到高性能 Linux 部署的全套优化策略。

---

## 2. 宏基因组 Agent 架构完善（System Architecture）

针对原始流程中缺失的**分箱（Binning/MAGs）**、**宿主去噪**以及**状态恢复机制**，优化后的系统架构如下：

```text
                                User Input
                                    |
                     "分析我的肠道宏基因组 FASTQ 数据"
                                    |
                                    v
┌────────────────────────────────────────────────────────────────────────┐
│                        Metagenome Coordinator Agent                     │
│  - Task Decomposition (DAG Generator)  - Environment & Resource Manager│
│  - Context Memory (File paths, Samples) - Human-in-the-Loop Checkpoint │
└───────────────────────────────────┬────────────────────────────────────┘
                                    | (Planner Rules & Task Graph)
                                    v
                 ┌──────────────────────────────────────┐
                 │       Pipeline Execution Engine      │
                 │  (Nextflow / Snakemake Execution)    │
                 └──────────────────┬───────────────────┘
                                    |
    ┌───────────────────────────────┼───────────────────────────────┐
    │                               │                               │
    v                               v                               v
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│ Dynamic Execution Layer │   │ Dynamic Execution Layer │   │ Dynamic Execution Layer │
│      [Data Preproc]     │   │     [Taxonomy Profile]  │   │   [Assembly & MAGs]     │
├─────────────────────────┤   ├─────────────────────────┤   ├─────────────────────────┤
│ QC & Host Removal Agent │   │ Classification Agent    │   │ Assembly & Binning Agent│
│  - FastQC / fastp       │   │  - Kraken2 + Bracken    │   │  - MEGAHIT / metaSPAdes │
│  - Bowtie2 (Remove HG38)│   │  - MetaPhlAn4           │   │  - MetaBAT2 / MaxBin2   │
│  - Kneaddata            │   │  - Humann3 (Functional) │   │  - CheckM2 / GTDB-Tk    │
└───────────┬─────────────┘   └───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │                             │
            └─────────────────────────────┼─────────────────────────────┘
                                          |
                                          v
                              ┌──────────────────────┐
                              │  Intermediate Logic  │
                              │  Correction / Retry  │<--- [Validator Loop]
                              └───────────┬──────────┘
                                          |
                                          v
                              ┌──────────────────────┐
                              │  Downstream Analytics│
                              ├──────────────────────┤
                              │ Statistical & Bio Agent│
                              │  - R (phyloseq, LEfSe)│
                              │  - Python (Scikit-bio)│
                              │  - DESeq2 / Maaslin2 │
                              └───────────┬──────────┘
                                          |
                                          v
                              ┌──────────────────────┐
                              │    Report Agent      │
                              ├──────────────────────┤
                              │  - LLM Bio Interpreter│
                              │  - MultiQC Summarizer│
                              │  - Interactive Web/PDF│
                              └──────────────────────┘
```

---

## 3. 核心功能层优化细节

### 3.1 引入组学关键环节（MAGs与宿主去除）
* **宿主去噪**：增加 `Bowtie2` / `Kneaddata` 比对到人类参考基因组（hg38）消除宿主污染，保障数据的隐私与准确性。
* **单菌基因组（MAGs）分析**：将拼接后的 Contigs 进行 Binning 分箱（`MetaBAT2`, `MaxBin2`, `DAS Tool`），并通过 `CheckM2` 评估基因组完整度/污染度，最后使用 `GTDB-Tk` 进行精确定位。

### 3.2 任务调度与“自愈”纠错机制（Self-Correction Loop）
* **解耦规划与执行**：Agent 负责高层拓扑规划（Planner），具体生信任务由 **Nextflow** 或 **Snakemake** 执行，避免单步 Shell 崩溃引发的整个进程中断。
* **结构化日志捕获与降级重试**：
  * 捕获生信工具的 Error Code（例如 `Exit Code 137` 代表 Out-Of-Memory）。
  * 自动触发Heuristic规则（如将 `metaSPAdes` 降级为 `MEGAHIT`，或减少线程与内存占用的参数后再试）。

### 3.3 生物学 RAG 增强与自动化统计
* **R/Python 统计沙箱**：基于 R 语言 (`phyloseq`, `microeco`, `DESeq2`) 自动运行 Alpha/Beta 多样性与差异菌群分析。
* **知识库与文献溯源（RAG）**：连接 Gut Microbe KB / PubMed 微生物组文献库，为差异菌群（如 *Akkermansia muciniphila*）提供生物学解释和文献引用。

---

## 4. Linux 服务器生产环境部署调优

### 4.1 核心架构演进：从 Mac 转向 Linux 高性能节点

```text
 ┌─────────────────────────────────────────────────────────────┐
 │            Web UI / CLI / REST API (FastAPI)                │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                v
 ┌─────────────────────────────────────────────────────────────┐
 │                Linux Agent Hub (Python)                     │
 │  • LLM Engine: vLLM / Ollama / Cloud API                    │
 │  • Execution Engine: Celery / ProcessPool / Nextflow        │
 └──────────────────────────────┬──────────────────────────────┘
                                │
    ┌───────────────────────────┼───────────────────────────┐
    │ (Process Slurm / Local)   │ (Condas/Containers)       │ (NVMe/RAM Storage)
    v                           v                           v
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│ System Tool 1 │           │ System Tool 2 │           │ Large DB Index│
│  - fastp      │           │  - Kraken2    │           │  - GTDB       │
│  - MEGAHIT    │           │  - MetaBAT2   │           │  - NCBI NT/NR │
└───────────────┘           └───────────────┘           └───────────────┘
```

### 4.2 Linux 环境下的落地关键策略

1. **推理引擎与接口分流**：
   * 本地 GPU 服务器使用 **vLLM** / **TGI** 部署开源大模型（如 `Qwen2.5-Coder-32B`）。
   * 纯算力服务器对接 API（如 DeepSeek/OpenAI API），将全部 GPU/CPU 算力留给拼接与比对任务。
2. **异步任务队列（Celery + Redis / Nextflow）**：
   * 彻底放弃同步阻塞（Synchronous blocking）模式，Agent 提交任务后异步监听进度。
3. **内存共享与比对加速 (`/dev/shm`)**：
   * 将大型数据库（如 Kraken2 标准库 70GB+）预载到 Linux 内存盘 `/dev/shm`，比对速度提升 10 倍以上。
4. **支持 HPC 集群调度 (Slurm / PBS)**：
   * 在超算环境下，Agent 具备自动生成与提交 `.sbatch` 投递脚本的能力。

---

## 5. Linux 环境下 Agent 工具封装（Python 代码示例）

```python
import subprocess
import shlex
import logging

class LinuxBioToolRunner:
    """
    Linux 生产环境下基于 Bioconda 环境隔离的生信工具执行器
    """
    def __init__(self, conda_env: str = "metagenomics"):
        self.conda_env = conda_env

    def run_command(self, cmd: str, timeout: int = 3600) -> dict:
        # 使用 conda run 隔离各模块的依赖库
        full_cmd = f"conda run -n {self.conda_env} {cmd}"
        logging.info(f"[Executing Command]: {full_cmd}")
        
        try:
            result = subprocess.run(
                shlex.split(full_cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=True
            )
            return {"status": "success", "stdout": result.stdout}
        except subprocess.CalledProcessError as e:
            # 捕获日志发还给 Agent 进行自愈与重试
            logging.error(f"[Tool Error]: {e.stderr}")
            return {"status": "failed", "error": e.stderr}
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": f"Command timed out after {timeout}s"}

# 示例：Kraken2 物种比对调用
def run_kraken2_species_profiling(fastq_1: str, fastq_2: str, db_path: str = "/dev/shm/kraken2_db", threads: int = 32):
    runner = LinuxBioToolRunner(conda_env="kraken2_env")
    cmd = f"kraken2 --db {db_path} --threads {threads} --paired {fastq_1} {fastq_2} --report kraken_report.txt"
    return runner.run_command(cmd)
```

---

## 6. 总结与路线图

1. **短期**：将 Agent 的命令行执行器改造为 Bioconda 隔离环境调用，引入 `Bowtie2` 与 `MetaBAT2` 补全核心流程。
2. **中期**：将底层的实际计算工作流迁移至 **Nextflow**，由 Agent 负责动态生成 Nextflow 配置文件（Config）。
3. **长期**：在 Linux 服务器上集成挂载学术数据库的 RAG 模块，实现“**数据输入 -> 拼接分类 -> 差异分析 -> 带有文献佐证的报告**”全自动闭环。
