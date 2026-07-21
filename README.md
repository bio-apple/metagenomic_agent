# Metagenomic Research Agent

**版本** `0.9.0` · 容器沙盒工具调用（Docker/Apptainer）+ 报错自愈 · 专业化多智能体科研平台。

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

| 路径 | 含义 |
|------|------|
| `router_decision.json` | 意图与领域路由 |
| `tool_specialist/tool_commands.md` | 精确工具命令 |
| `plan_validation.json` | 方案完备性 / 领域追问 |
| `workflow/generated.nf` · `.smk` | RAG 生成的工作流草稿 |
| `evidence/evidence_table.md` | 文献证据表 |
| `xai/feature_importance.md` | 标志物可解释归因 |
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
