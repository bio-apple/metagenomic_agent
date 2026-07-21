# Metagenomic Agent

基于 **LangGraph** 的宏基因组生信 Agent（MVP）：自然语言需求 → 条件化分析 DAG → 专用 BioAgent 集群 → 校验回环 → HTML 报告。

## 架构（MVP 裁剪）

```
Input Parser → Coordinator (DAG) → BioAgent Swarm (QC / Taxonomy / Functional)
      → Validator Loop (retry) → Report Agent → HTML / methods / reproduce.sh
```

暂缓：完整 Nextflow、组装分箱实装、基因组语言模型、下游多组学、Web HITL。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 可选：配置 DeepSeek/Qwen API

# mock 模式（无需 Docker / 数据库）
meta-agent run --input tests/fixtures/fastq --outdir ./results --mode mock --yes
```

打开 `results/report/report.html` 查看交互式报告。

## Docker 模式

需本地可用镜像（默认 `meta:latest`，可与旁路 [metagenomics](../metagenomics) 项目对齐），并在 `config/default.yaml` 填写：

- `paths.host_index`
- `paths.kraken2_db`

```bash
meta-agent run -i /data/fastq -o ./results --mode docker --yes
```

## LLM

通过 OpenAI 兼容接口（DeepSeek / Qwen）：

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPENAI_MODEL=deepseek-chat
```

未配置 API Key 时，Coordinator 使用内置肠道宏基因组默认流水线模板。

## 测试

```bash
pytest -q
```

## 目录

- `src/metagenomic_agent/` — 核心包（graph / agents / tools / validators / report）
- `config/default.yaml` — 默认配置
- `examples/` — 示例配置
- `tests/` — 单元与 dry-run 测试
