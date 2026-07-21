# Metagenomic Research Agent

面向科学问题的自主宏基因组分析 Agent（LangGraph 多 Agent 协作），不依赖任何既有私有流水线仓库。

设计文档：[`docs/Metagenomic_Research_Agent_Developer_Documentation.md`](docs/Metagenomic_Research_Agent_Developer_Documentation.md)

## 思路

- **Supervisor** 把自然语言问题拆成任务图
- **专用 Agent**（QC / Taxonomy / Assembly / Function / Statistics）调用工具
- **Critic** 做可靠性审查并可触发重试
- **Literature** 连接机制解释与文献
- **Report** 产出可复现报告

工具执行三态（`ToolContext`）：

| mode | 行为 |
|------|------|
| `mock` | 无外部依赖，生成可演示产物（默认） |
| `local` | 调用本机 PATH 上的 fastp/kraken2/... |
| `docker` | 使用公开 biocontainers 镜像（可在 config 覆盖） |

## 快速开始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 可选：配置 LLM

meta-agent run \
  --input tests/fixtures/fastq \
  --outdir ./results \
  --mode mock \
  --query "Analyze shotgun metagenomic samples from IBD patients and healthy controls. Identify microbial biomarkers." \
  --yes
```

产物：

```
results/
├── quality_report.html
├── taxonomy_profile.tsv
├── functional_profile.tsv
├── diversity_analysis/
├── biomarkers/
├── literature_summary/
└── final_report.html
```

## API / Snakemake

```bash
meta-agent serve --host 127.0.0.1 --port 8000
snakemake -j 2 --snakefile workflow/Snakefile
```

## 配置

见 [`config/default.yaml`](config/default.yaml)：数据库路径、`docker.images`、流水线开关。

## 测试

```bash
pytest -q
```
