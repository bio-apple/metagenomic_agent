# 架构说明（v0.8 · 多智能体）

## 设计动机

从“单模型包办”升级为**专业化多智能体协同**（参考 OpenBioLLM / BioAgents / s2f-agent）：

| 角色 | 模块 | 职责 |
|------|------|------|
| Router Agent | `agents/router_agent.py` | 意图理解与领域分发 |
| Tool Specialist | `agents/tool_specialist.py` | 精确命令/参数（领域 KB） |
| Plan Validator | `agents/plan_validator.py` | 方案完备性与领域约束；缺信息则追问 |
| Supervisor / Swarm | `supervisor` + QC/Tax/… | 执行层专家 |
| Workflow Agent | `agents/workflow_agent.py` | nf-core/Snakemake RAG 生成 + 报错反思 |
| XAI | `evaluation/xai.py` | 标志物特征归因（SHAP/LIME 风格） |

## 主链路

```
parse → router → supervisor → tool_specialist → plan_validator
     → export_dag → workflow_agent → contract_check → HITL → swarm
     → validate → quality → self-heal* → critic → literature
     → pi_review* → visualization → xai → report
```

## 领域知识与约束

- 工具擅长领域：`knowledge/tool_domain_kb.json`（含 CAMITAX/TAMA/ViWrap/PhaBOX 等路由注册）
- 安全优先：缺宿主基因组版本、坐标系统、分组元数据时**追问**，不瞎猜（`domain_kb.missing_domain_constraints`）
- 配置：`validation.plan_validator_hard_fail`

## 工作流 RAG

- 语料：`knowledge/workflow_snippets.json`（nf-core/mag、taxprofiler 等）
- 检索：`knowledge/workflow_rag.py`
- 产出：`workflow/generated.nf`、`generated.smk`，以及基于错误的 `workflow_reflection.md`

## XAI

对差异属做 leave-one-feature 组间分离度归因 → `xai/feature_importance.md`（无重度 ML 依赖的可解释近似）。

## 包结构速查

```text
agents/     router, tool_specialist, plan_validator, workflow_agent, …
knowledge/  tool_domain_kb.json, workflow_snippets.json, domain_kb.py
evaluation/ xai.py, quality_score.py, benchmarks.py
```
