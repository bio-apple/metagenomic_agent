# 架构说明

面向 **v0.13**。用法见 [USAGE.md](USAGE.md)；能力缺口与规划见 [ROADMAP.md](ROADMAP.md)。

## 设计：从 Wrapper 到 Bio Reasoning

```
User
  → Requirement Understanding (Router)
  → Biological Reasoning Layer
  → Workflow Planning (Supervisor / Tool Specialist / Validator)
  → Tool Execution (Swarm + Sandbox)
  → Result Interpretation (Tax/Function notes + Evidence + Literature)
  → Scientific Report
```

| 角色 | 模块 | 职责 |
|------|------|------|
| Router | `router_agent.py` | 意图与领域 |
| **Bio Reasoning** | `bio_reasoning_agent.py` | 研究目标、assay、流程、组装策略、HITL 选项 |
| Supervisor (PM) | `supervisor.py` | 任务分解（消费 bio_reasoning） |
| Tool Specialist | `tool_specialist.py` | 精确命令 |
| Plan Validator | `plan_validator.py` | 完备性追问 |
| QC / Taxonomy / Assembly / Function / Stats | 对应 agents | 执行 + 生物学解释 |
| Critic / Literature / PI / Viz / Report | 对应模块 | 审核、证据、手稿、仪表盘 |

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → export_dag → workflow_agent → contract → HITL
  → swarm → validate → quality → HITL(runtime) → self-heal*
  → critic → literature → pi* → visualization → xai → report
```

## 关键模块

| 主题 | 路径 |
|------|------|
| 生物学推理 | `agents/bio_reasoning_agent.py` |
| HITL 多方案 | `agents/hitl.py` |
| 工具沙盒 / 自愈 | `tools/sandbox.py` · `execution/self_heal.py` |
| 权威 RAG / 证据链 | `rag/authority.py` · `knowledge/evidence_chain.py` |
| 摘要上下文 | `coordinator/summary.py` |
| 可复现导出 | `report/workflow_export.py` |
| 交互可视化 | `report/interactive.py` |

## 包结构

```text
agents/        bio_reasoning + swarm specialists
skills/        契约、playbooks、bandit
knowledge/     领域 KB、best_practices
rag/           curated 生物库
coordinator/   memory、summary
stats/ tools/ validators/ execution/ report/ evaluation/ api/
```
