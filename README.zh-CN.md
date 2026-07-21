> English: [README.md](README.md)

# Metagenomic Research Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.24.0-0B6E4F.svg)](CHANGELOG.md)

**面向 shotgun 宏基因组的自主 AI 科学家** — 多智能体规划、容器沙箱工具执行、有据解读与可重复报告。

公开仓库：[github.com/bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 图摘要

![Graphical abstract: Input → Plan+HITL → Execute Swarm with Self-Heal → Interpret → Report](docs/figures/overview.png)

<p align="center"><em>Figure 1.</em> 从 FASTQ / 研究问题到经审计报告的端到端工作流。高风险自愈动作与重度计算步骤由人在回路（HITL）门控。矢量源：<a href="docs/figures/overview.svg"><code>overview.svg</code></a>。</p>

<details>
<summary>文字概览（无障碍）</summary>

```text
Input (FASTQ, query, metadata)
  → Plan + HITL (router, bio-reasoning, planner, DAG / params.yaml)
  → Execute Swarm (QC · Taxonomy · Function · Resistance · Stats · MAG)
       ↺ Validate → Self-Heal (safe auto-fix; high-risk → HITL)
  → Interpret (Critic · Literature · Evidence/KG · Reviewer · Reflection · XAI)
  → Output (final_report.html, Methods, biomarkers, MetaAgentScore, audits)
```

</details>

## 亮点

- **研究问题驱动**，非固定流水线包装器：意图 → 校验 DAG → 沙箱生物信息工具。
- **证据落地**：物种 / *p* / *q* / 效应量绑定程序表；混合 RAG + 微生物组知识图谱。
- **自愈与可靠性控制**：资源/平台重试自动进行；有生物学后果的纠正需 HITL（[docs/SELF_HEAL.zh-CN.md](docs/SELF_HEAL.zh-CN.md)）。
- **先天可重复**：引擎 `params.yaml`、Methods 导出、审稿人一键 mock 演示。

**范围：** 仅 shotgun / 相关宏基因组。不做多组学扩展。

## 代码与数据可用性

| Resource | Location |
|----------|----------|
| Source code | 本仓库（公开） |
| License | [MIT](LICENSE) |
| Citation | [CITATION.cff](CITATION.cff) |
| Reviewer demo data | [examples/demo_data/](examples/demo_data/) |
| One-click reproduce | [`bash scripts/reproduce_demo.sh`](scripts/reproduce_demo.sh) |
| Tests | [`pytest`](tests/) |

材料不“应要求提供”。内置演示使用 `--mode mock` 做**软件**可重复性；生产分析需参考数据库（[database/README.zh-CN.md](database/README.zh-CN.md)）。

## 快速开始

生产路径分 **三步**：软件部署（Docker）→ 本地下载参考数据库 → 运行 Agent。

### 1. 软件部署（Docker）

参考库**不会**打进镜像（体积过大）。只构建编排层：

```bash
git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent

docker compose up --build -d
# API / Web UI: http://127.0.0.1:8000/ui
```

可选：本地（非 Docker）安装，用于开发 / mock 演示：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
meta-agent version
```

要求：Docker Engine（推荐）或 Python ≥ 3.10。可选：`OPENAI_API_KEY`（LLM 增强路径）。大内存 Linux 说明：[docs/DEPLOY_LINUX.zh-CN.md](docs/DEPLOY_LINUX.zh-CN.md)。

### 2. 本地下载数据库

在**宿主机**（或共享文件系统）构建/下载参考库，再通过 `paths.*` 指向；数据库始终在镜像外。

```bash
export DB_ROOT=/ref/databases   # 或：$(pwd)/database
bash scripts/build_databases.sh --layout

# 生产最小集（示例 — 完整步骤见 database/README.zh-CN.md）：
#   宿主 Bowtie2 索引 → paths.host_index
#   Kraken2 标准库   → paths.kraken2_db   （设置 KRAKEN_TARBALL_URL 后 --kraken-download）
#   MetaPhlAn        → paths.metaphlan_db （--metaphlan）
bash scripts/build_databases.sh --check
```

将 `$DB_ROOT/PATHS.example.yaml` 合并进 `config/site.yaml`（使用绝对路径）。  
完整配方：[database/README.zh-CN.md](database/README.zh-CN.md)。

使用真实库启动 Compose：

```bash
META_REF=/ref/databases docker compose up --build -d
```

### 3. 运行 Agent

**冒烟 / 审稿演示**（无需参考库；mock 工具）：

```bash
bash scripts/reproduce_demo.sh
# 或：
meta-agent run \
  -i examples/demo_data/fastq \
  --metadata examples/demo_data/metadata.tsv \
  -o ./results/demo --mode mock --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"
# → results/demo/final_report.html
```

**生产**（真实工具 + 本地库，Docker/Apptainer）：

```bash
meta-agent run -i /data/fastq -o /data/out --mode docker \
  -c config/site.yaml --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

Web UI / API（`docker compose up` 或本地 `serve` 之后）：

```bash
meta-agent serve --host 127.0.0.1 --port 8000
# → http://127.0.0.1:8000/ui
```

CLI 细节：[docs/USAGE.zh-CN.md](docs/USAGE.zh-CN.md)。

## 文档

| Document | Contents |
|----------|----------|
| [docs/USAGE.zh-CN.md](docs/USAGE.zh-CN.md)（[English](docs/USAGE.md)） | CLI、API、配置、输出 |
| [docs/ARCHITECTURE.zh-CN.md](docs/ARCHITECTURE.zh-CN.md)（[English](docs/ARCHITECTURE.md)） | Agent、落地、HITL、评估 |
| [docs/SELF_HEAL.zh-CN.md](docs/SELF_HEAL.zh-CN.md)（[English](docs/SELF_HEAL.md)） | 自愈 FPR 分析与 HITL 策略 |
| [docs/DEPLOY_LINUX.zh-CN.md](docs/DEPLOY_LINUX.zh-CN.md)（[English](docs/DEPLOY_LINUX.md)） | Linux ≥256 GB / HPC 部署 |
| [database/README.zh-CN.md](database/README.zh-CN.md)（[English](database/README.md)） | 参考库布局与**构建步骤** |
| [examples/demo_data/README.zh-CN.md](examples/demo_data/README.zh-CN.md)（[English](examples/demo_data/README.md)） | 审稿演示数据 |
| [docs/manuscript/README.zh-CN.md](docs/manuscript/README.zh-CN.md)（[English](docs/manuscript/README.md)） | 手稿草稿索引 |
| [docs/manuscript/application_note.md](docs/manuscript/application_note.md) | **Application Note** 手稿草稿（仅英文） |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史（仅英文） |

## 引用

请引用本仓库与 `CITATION.cff`。期刊引用将在发表后补充。

## 许可证

[MIT](LICENSE) — © 2026 bio-apple contributors。
