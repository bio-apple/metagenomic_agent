# 架构说明（v0.5 实现）

本文描述**仓库当前代码**的结构，而非早期设计稿。源码根目录：`src/metagenomic_agent/`。

## 分层总览

```text
┌─────────────────────────────────────────────────────────────┐
│  Interfaces: CLI (meta-agent) · FastAPI (/analyze)          │
├─────────────────────────────────────────────────────────────┤
│  Orchestration: LangGraph (graph.py)                        │
│  parse → supervisor → contract_check → hitl → execute_swarm │
│       → validate → self_heal* → critic → literature → report│
├──────────────┬──────────────────────┬───────────────────────┤
│ Agents       │ Skills / Contracts   │ Tools / Runtime       │
│ supervisor   │ registry, playbooks  │ fastp, kraken, …      │
│ qc/tax/asm…  │ checker, router      │ glm, linux_runner     │
│ critic/lit…  │ bandit (ε-greedy)    │ ToolContext modes     │
├──────────────┴──────────────────────┴───────────────────────┤
│ Validators · Knowledge (IBD KB, RAG) · Report + CWL         │
│ Execution: executor, self_heal, monitor, optional engines   │
└─────────────────────────────────────────────────────────────┘
```

## 图节点职责

| 节点 | 模块 | 职责 |
|------|------|------|
| `parse_input` | `input/parser.py` | 发现样本、读长等输入特征 |
| `supervisor` | `agents/supervisor.py` | 任务分解与 DAG / playbook 选择 |
| `contract_check` | `skills/checker.py` | 技能前置契约；失败可挂 HITL |
| `hitl` | `agents/hitl.py` | 人机确认或自动通过 |
| `execute_swarm` | `execution/executor.py` | 按 DAG 调度专用 Agent |
| `validate` | `validators/loop.py` | 技术 QC + 生物学上下文检查 |
| `self_heal` | `execution/self_heal.py` 等 | 参数降级、工具切换、有限次重试 |
| `critic` | `agents/critic_agent.py` | 可靠性与契约/生物警告汇总 |
| `literature` | `agents/literature_agent.py` | PubMed / RAG 辅助 |
| `report` | `report/generator.py` | 报告 + `reproducibility` 包 |

## Skill / Contract / Playbook

- **Skill**：工具封装（输入/输出契约），见 `skills/registry.py`
- **Contract**：`skills/contracts.py` 中的 pre/post 条件
- **Playbook**：强制步骤序列（如 taxonomy_profiling、mag_recovery、ibd_biomarker），见 `skills/playbooks.py`
- **路由**：`skills/router.py` — 长读长（≥5000 bp）优先 gLM；短读长经典工具；可选双路融合
- **Bandit**：`skills/bandit.py` — 按历史 match/quality 做 ε-greedy 选择

## 工具运行时

`tools/context.py` 的 `ToolContext` 统一 `mock|local|conda|docker`。真实二进制通过 `linux_runner` / `docker_runner` 调用；gLM 适配在 `tools/glm.py`。

## 验证与知识

- 技术：`validators/technical.py`
- 生物学：`validators/biological.py` + `knowledge/ibd_biomarker_kb.json`
- 自愈动作：`validators/recovery.py`

## 部署扩展（可选）

- `deployment/celery_app.py`、`deployment/slurm.py`
- `workflow/Snakefile`、`workflow/nextflow/`
- `execution/engine.py`：可切换外部引擎产物（默认仍为 LangGraph 进程内执行）

## 包结构速查

```text
src/metagenomic_agent/
  agents/          # 专用智能体
  skills/          # 契约、剧本、路由、bandit
  tools/           # 生信与 gLM 适配
  validators/      # 技术 + 生物学验证
  execution/       # 调度、监控、自愈
  report/          # 报告与 CWL
  knowledge/       # KB / RAG 文本
  api/             # FastAPI
  evaluation/      # 基准指标辅助
```

设计动机与代码落地表见 [OPTIMIZATION_PROPOSAL_IMPL.md](OPTIMIZATION_PROPOSAL_IMPL.md) 与 [PROPOSAL_2026_IMPL.md](PROPOSAL_2026_IMPL.md)。

### v0.6–0.7 图节点增量

- `export_dag` / `quality_scores` / `visualization`
- `literature`：Evidence Table + bio-DB RAG
- `pi_review`：PI Agent 可选复盘重跑
