# 架构说明

面向 **v0.12**。用法见 [USAGE.md](USAGE.md)。

源码根目录：`src/metagenomic_agent/`。

## 设计

从单模型包办改为**专业化多智能体**（LangGraph 编排）：规划 → 执行 Swarm → 审核 → 解释 → 报告。

| 角色 | 模块 | 职责 |
|------|------|------|
| Router | `agents/router_agent.py` | 意图与科学领域 |
| Tool Specialist | `agents/tool_specialist.py` | 工具命令/参数 |
| Plan Validator | `agents/plan_validator.py` | 完备性；缺元数据追问 |
| Supervisor + Swarm | `supervisor` + QC/Tax/Asm/… | 执行专家 |
| Workflow Agent | `agents/workflow_agent.py` | 工作流 RAG + 反思 |
| Critic / Literature / PI | 对应 agents | 质控、证据、复盘 |
| Visualization / XAI | `visualization_agent` · `evaluation/xai.py` | 交互图与归因 |
| Report | `report/generator.py` · `interactive.py` | HTML / 手稿 / 仪表盘 / CWL |

```
parse → router → supervisor → tool_specialist → plan_validator
  → export_dag → workflow_agent → contract → HITL → swarm
  → validate → quality → self-heal*
  → critic → literature → pi_review* → visualization → xai → report
```

```text
CLI / FastAPI
    ↓
LangGraph（规划智能体 → Swarm → Critic/PI → XAI → Report）
    ↓
Skills/契约 · 领域 KB · 生物 RAG · Tools/Stats · 沙盒执行
```

## 关键模块

| 主题 | 路径 | 说明 |
|------|------|------|
| 工具沙盒 | `tools/sandbox.py` · `docker_runner.py` · `context.py` | 强类型工具调用；优先容器 |
| 错误自愈 | `execution/self_heal.py` · `linux_runner.classify_error` | oom/arch/缺二进制等 |
| 权威 RAG | `rag/authority.py` · `rag/data/curated_bio_index.json` | GTDB/NCBI/KEGG/UniProt/CARD |
| 证据链 | `knowledge/evidence_chain.py` | 丰度·p/q·DB ID·PMID |
| 摘要上下文 | `coordinator/summary.py` · `memory.llm_safe_view` | 禁止序列入窗 |
| 可复现导出 | `report/workflow_export.py` · `reproducibility.py` | `.nf`/`.smk`/seed/manifest |
| 交互可视化 | `report/interactive.py` | Plotly 多图 + q 筛选 |
| 领域约束 | `knowledge/domain_kb.py` · `tool_domain_kb.json` | 宿主版本/坐标/分组 |
| 工作流 RAG | `knowledge/workflow_rag.py` · `workflow_snippets.json` | nf/smk 片段 |
| 统计 | `stats/` | PCoA、共现、LEfSe/ANCOM 近似 |

## 包结构

```text
agents/        多智能体
skills/        契约、playbooks、gLM 路由、bandit
knowledge/     领域 KB、best_practices、工作流片段
rag/           生物库 curated 检索
coordinator/   memory、summary
stats/         多样性与差异近似
tools/         fastp、kraken、沙盒…
validators/    技术/生物学校验
execution/     executor、DAG、自愈、monitor
report/        HTML、interactive、manuscript、CWL
evaluation/    quality、xai、benchmarks
api/           FastAPI
```
