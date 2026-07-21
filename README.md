# Metagenomic Research Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![GitHub](https://img.shields.io/badge/GitHub-bio--apple%2Fmetagenomic__agent-181717?logo=github)](https://github.com/bio-apple/metagenomic_agent)

**Version** `0.23.1` — multi-agent AI Scientist for shotgun metagenomics (planning · execution · review · KG · reproducible reports).

**Repository (public):** [https://github.com/bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

---

## Code and data availability

| Item | Location |
|------|----------|
| Source code | Public GitHub: [bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent) |
| License | **MIT** — see [`LICENSE`](LICENSE) |
| Citation metadata | [`CITATION.cff`](CITATION.cff) |
| One-click demo data | [`examples/demo_data/`](examples/demo_data/) (tiny paired FASTQ + phenotype TSV) |
| Unit / integration tests | [`tests/`](tests/) · CI smoke via `pytest` |
| Reproduce script | [`scripts/reproduce_demo.sh`](scripts/reproduce_demo.sh) |

All materials needed to install, run the mock end-to-end demo, and execute the automated test suite are **in this repository**. No email request is required.

> **Scope of the bundled demo:** `--mode mock` synthesizes tool outputs for software / pipeline reproducibility. It does **not** replace real Kraken2 / MetaPhlAn / GTDB reference databases. For production runs, build databases per [`database/README.md`](database/README.md) and use `docker` or `apptainer`.

---

## 许可证（License）

本软件以 **MIT License** 发布。完整条款见根目录 [`LICENSE`](LICENSE)。`pyproject.toml` 中的 `license = { text = "MIT" }` 与之一致。

---

## 环境要求

- Python **≥ 3.10**
- macOS / Linux（推荐 Linux；生产部署见 [`docs/DEPLOY_LINUX.md`](docs/DEPLOY_LINUX.md)）
- （可选）Docker / Apptainer、OpenAI 兼容 API（`OPENAI_API_KEY`）—— mock 演示**不需要**

---

## 安装（一步步）

```bash
# 1. 克隆公开仓库
git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent

# 2. 建议使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. 可编辑安装（含开发/测试依赖）
pip install -e ".[dev]"

# 4. 确认 CLI
meta-agent version
```

可选：复制 `.env.example` 为 `.env` 并填写 `OPENAI_API_KEY`（仅 LLM 增强路径需要；mock 演示可跳过）。

---

## 一键复现（审稿人推荐）

无需参考库、无需 GPU。在仓库根目录执行：

```bash
bash scripts/reproduce_demo.sh
```

该脚本会依次：

1. 必要时执行 `pip install -e ".[dev]"`
2. 运行 `pytest -q`
3. 用内置演示数据跑完整 mock 流水线
4. 检查报告文件是否生成

等价手动命令：

```bash
pip install -e ".[dev]"
pytest -q

meta-agent run \
  -i examples/demo_data/fastq \
  --metadata examples/demo_data/metadata.tsv \
  -o ./results/demo \
  --mode mock --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"

# 打开报告
open ./results/demo/final_report.html   # Linux: xdg-open …
```

演示数据说明：[`examples/demo_data/README.md`](examples/demo_data/README.md)。

最小单样本 fixture（CI 亦使用）：`tests/fixtures/fastq/`。

---

## 常用命令

```bash
# Web UI + API
meta-agent serve --host 127.0.0.1 --port 8000
# 浏览器打开 http://127.0.0.1:8000/ui

# Docker Compose（编排层）
docker compose up --build

# 真实数据（需参考库 + 容器）
meta-agent run -i /data/fastq -o /data/out --mode docker \
  -c config/default.yaml --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

更多 CLI / API / 配置：[`docs/USAGE.md`](docs/USAGE.md)。

---

## 流水线（摘要）

```
Planner → HITL → Swarm(QC / Taxonomy / Function / Resistance / Stats)
  → Critic → Literature → Evidence → Reviewer → Reflection → Report
```

---

## 文档

| 文档 | 用途 |
|------|------|
| [docs/USAGE.md](docs/USAGE.md) | CLI / API / 配置 / 产物 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与设计 |
| [docs/SELF_HEAL.md](docs/SELF_HEAL.md) | Self-Heal 假阳性分析与 HITL 防呆 |
| [docs/DEPLOY_LINUX.md](docs/DEPLOY_LINUX.md) | Linux ≥256 GB 部署 |
| [database/README.md](database/README.md) | 参考库目录与**构建步骤** |
| [examples/demo_data/README.md](examples/demo_data/README.md) | 演示数据 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |

---

## Citing

If you use this software, please cite the GitHub repository and `CITATION.cff`. A journal citation will be added upon publication.
