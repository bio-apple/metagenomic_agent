# 架构说明

面向 **v0.16**。详见 [USAGE.md](USAGE.md)、[ROADMAP.md](ROADMAP.md)。

## 设计

```
User → Router → Bio Reasoning (SOP + tool-manual RAG)
     → Supervisor → Tool Specialist → Plan Validator
     → Planner（实验设计 → 整体 Pipeline）
     → params.yaml → Executor（HPC Slurm / K8s Job + swarm/nf/smk）
     → QC & Critic（Q20/Q30 · Contamination · CheckM）
     → Literature → Reporter（Alpha/Beta · KEGG/COG/GO 解读）
     → Viz → final report
```

| 角色 | 模块 |
|------|------|
| Planner | `agents/planner_agent.py` |
| Executor / Bioinfo | `agents/executor_agent.py` |
| QC & Critic | `agents/critic_agent.py`（+ `qc_agent` 执行层） |
| Reporter | `agents/reporter_agent.py` |
| 工具手册 RAG | `knowledge/tool_manuals.json` · `domain_rag.py` |
| SOP RAG | `knowledge/sop_best_practices.json` |

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → planner → export_dag → workflow_agent → HITL
  → executor(swarm) → validate → quality → HITL → qc_critic → …
  → literature → visualization → reporter → xai → report
```
