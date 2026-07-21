# 架构说明（v0.9 · 多智能体 + 容器沙盒）

源码：`src/metagenomic_agent/`。

## 设计动机

从单模型包办升级为**专业化多智能体协同**（参考 OpenBioLLM / BioAgents / s2f-agent）：

| 角色 | 模块 | 职责 |
|------|------|------|
| Router | `agents/router_agent.py` | 意图与领域分发 |
| Tool Specialist | `agents/tool_specialist.py` | 精确命令/参数 |
| Plan Validator | `agents/plan_validator.py` | 完备性检查；缺信息追问 |
| Supervisor + Swarm | `supervisor` + QC/Tax/Asm/… | 执行层专家 |
| Workflow Agent | `agents/workflow_agent.py` | nf-core/Snakemake RAG + 反思 |
| Critic / Literature / PI | 对应 agents | 质控、证据、复盘 |
| Visualization / XAI | `visualization_agent` · `evaluation/xai.py` | 图与可解释归因 |
| Report | `report/generator.py` | HTML / 手稿 / CWL |

## 主链路

```
parse → router → supervisor → tool_specialist → plan_validator
     → export_dag → workflow_agent → contract_check → HITL → swarm
     → validate → quality_scores → self-heal*
     → critic → literature → pi_review* → visualization → xai → report
```

## 分层示意

```text
┌─────────────────────────────────────────────────────────────┐
│  CLI / FastAPI                                              │
├─────────────────────────────────────────────────────────────┤
│  LangGraph：规划智能体（Router/Specialist/Validator）         │
│            → 执行 Swarm → 审核（Critic/PI）→ 解释（XAI）     │
├──────────────┬────────────────────┬─────────────────────────┤
│ Skills/契约  │ 领域 KB + 生物 RAG │ Tools / Stats / gLM     │
├──────────────┴────────────────────┴─────────────────────────┤
│ Report · CWL · Workflow 导出 · Benchmarks                   │
└─────────────────────────────────────────────────────────────┘
```

## 工具沙盒与自愈（v0.9）

| 组件 | 路径 | 作用 |
|------|------|------|
| MCP 风格工具调用 | `tools/sandbox.py` | `ToolCallRequest` / `ToolCallResponse` 强类型入参 |
| Docker / Apptainer | `tools/docker_runner.py` | `--platform`、`--memory`、`--cpus`；HPC 用 Apptainer |
| ToolContext | `tools/context.py` | `run_tool` 统一走沙盒 |
| 错误分类 | `tools/linux_runner.classify_error` | oom / arch / lib / missing_binary… |
| 自愈 | `execution/self_heal.py` | 降参、换容器、钉 amd64、可读摘要 |

原则：**不要让 Agent 在宿主机随意 shell**；优先 biocontainers；报错捕获后自动重试，不把 stderr 原样抛给用户。

- 工具擅长领域：`knowledge/tool_domain_kb.json`
- 约束逻辑：`knowledge/domain_kb.py`（缺宿主版本 / 坐标系统 / 分组则追问）
- 配置：`validation.plan_validator_hard_fail`

## 工作流 RAG 与 XAI

| 能力 | 位置 | 产出 |
|------|------|------|
| 片段语料 | `knowledge/workflow_snippets.json` | — |
| 检索 | `knowledge/workflow_rag.py` | — |
| 生成 | `agents/workflow_agent.py` | `workflow/generated.nf` / `.smk` |
| 特征归因 | `evaluation/xai.py` | `xai/feature_importance.md` |

## 包结构

```text
agents/       router, tool_specialist, plan_validator, workflow_agent, swarm…
skills/       contracts, playbooks, router(gLM), bandit, decision
knowledge/    tool_domain_kb, workflow_snippets, best_practices, IBD KB
rag/          生物数据库 curated 检索
stats/        PCoA, LEfSe-like, ANCOM-like, co-occurrence
tools/        fastp, kraken, glm, …
validators/   technical + biological
execution/    executor, dag_export, self_heal
report/       HTML, manuscript, CWL
evaluation/   quality, xai, benchmarks
```
