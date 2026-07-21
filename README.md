# Metagenomic Research Agent

**版本** `0.12.0` · 交互式 Plotly 分析仪表盘 · Summary 长上下文 · 抗幻觉证据链 · 容器沙盒。

仓库：[bio-apple/metagenomic_agent](https://github.com/bio-apple/metagenomic_agent)

## 主链路

```
parse → Router → Supervisor → Tool Specialist → Plan Validator
      → export_dag → Workflow Agent → contract → HITL → swarm
      → validate → quality → self-heal*
      → critic → literature → PI* → visualization → XAI → report
```

## 快速开始

```bash
git clone https://github.com/bio-apple/metagenomic_agent.git
cd metagenomic_agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

meta-agent run \
  -i tests/fixtures/fastq \
  -o ./results \
  --mode mock \
  --yes \
  -q "IBD gut metagenome biomarker discovery"

pytest -q
meta-agent version
```

## 运行模式

| Mode | 说明 |
|------|------|
| `mock` | 无数据库/二进制，结构完整演示（CI 默认） |
| `docker` / `apptainer` | **推荐**：biocontainers 隔离执行（规避 ARM/x86 与依赖地狱） |
| `conda` / `local` | 本机环境；缺库/架构错误时自愈可切回容器 |

生产建议：`mode=docker` 且 `sandbox.prefer_container=true`。Apple Silicon 默认 `sandbox.platform=linux/amd64`。

## 工具沙盒与自愈（v0.9）

- 工具经 `ToolCallRequest` 强类型入参调用，默认进 Docker/Apptainer，而非宿主机裸跑。
- 失败时分类 stderr（OOM / 缺二进制 / 架构不兼容 / 动态库缺失），自动降参、换组装器、切容器或 amd64，并向用户输出**可读摘要**而非原始堆栈。
- 配置见 `config/default.yaml` → `sandbox:`。

## 抗幻觉与证据链（v0.10）

- 分类单元须在 **GTDB / NCBI Taxonomy** 策展索引中锚定，否则 Literature / 解读拒绝陈述。
- 允许的陈述附带：**相对丰度**、**p/q 值**（若有差异检验）、**数据库 ID**（KEGG/UniProt/CARD 等）与 **PMID**。
- 产物：`evidence/claims.json` · `evidence/claims.md`；配置 `interpretation.require_grounding`。

## 长上下文与可复现（v0.11）

- Agent 只消费中间文件的**统计元数据**（Reads、Q30、N50、CheckM 完整度等），不把 Fastq/Bam/Fasta 序列塞进 Context Window。
- 分析结束后自动导出 `workflow/reproducible.nf` / `reproducible.smk`、`seeds.json`、`config_snapshot.yaml`。
- 配置：`summary.enabled`、`reproducibility.seed` / `auto_export`。

## 交互式可视化（v0.12）

- Plotly 仪表盘：物种组成堆叠图、Alpha/Beta 箱线图、PCoA、Heatmap、Volcano。
- Heatmap / Volcano 支持 **FDR q 滑块**实时筛选显著差异菌群。
- 入口：`interactive_dashboard.html`（报告内亦嵌入多图）。

| 路径 | 含义 |
|------|------|
| `router_decision.json` | 意图与领域路由 |
| `tool_specialist/tool_commands.md` | 精确工具命令 |
| `plan_validation.json` | 方案完备性 / 领域追问 |
| `workflow/generated.nf` · `.smk` | RAG 生成的工作流草稿 |
| `evidence/evidence_table.md` | 文献证据表 |
| `evidence/claims.md` | 抗幻觉证据链 |
| `context/pipeline_summary.json` | 统计元数据摘要（供 LLM） |
| `workflow/reproducible.nf` · `.smk` | 同行评审可复现工作流 |
| `workflow/seeds.json` | 运行种子 |
| `interactive_dashboard.html` | Plotly 交互式分析视图 |
| `report/manuscript/` | 投稿分节草稿 |
| `reproducibility/` | CWL + run_manifest |

## 文档

| 文档 | 用途 |
|------|------|
| [docs/README.md](docs/README.md) | 索引 |
| [docs/USAGE.md](docs/USAGE.md) | CLI / API / 配置 / 排障 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 多智能体架构 |
| [docs/METHODS.md](docs/METHODS.md) | 论文 Methods |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |
| [database/README.md](database/README.md) | 参考库路径 |

## 局限

- ViWrap/PhaBOX/CAMITAX/TAMA 等可为**路由注册**而不一定已安装；mock 下只记录拟执行命令。
- XAI 为组间分离度归因近似，非训练分类器上的完整 SHAP。
- 生物库 RAG / 工作流 RAG 使用 curated 语料；全量库与 nf-co.re 需自备挂载。
- `mock` 结果不可作生物学结论。

## License

MIT
