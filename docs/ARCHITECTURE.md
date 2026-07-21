# 架构说明（v0.21）

CLI / 配置 / 产物见 [USAGE.md](USAGE.md)；Linux ≥256 GB 部署见 [DEPLOY_LINUX.md](DEPLOY_LINUX.md)；短板闭环见 [OPTIMIZATION.md](OPTIMIZATION.md)。

## 编排主链

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → planner → export_dag(+critical HITL gates) → workflow_agent → contract
  → HITL (sync Prompt | async 落盘暂停)
  → executor (swarm / nf|smk + HPC) → validate → quality → HITL(runtime)
  → self-heal* → critic(bio_qc) → literature → pi_review → viz
  → reporter → xai → report
```

异步审批后续跑：`resume_pipeline` 从 `execute_swarm` 起。

## 角色与模块

| 角色 | 职责 | 主要路径 |
|------|------|----------|
| Planner | 实验设计、assay/环境、整体 DAG | `agents/planner_agent.py` |
| Executor | 资源感知、调度规格、swarm/引擎执行 | `agents/executor_agent.py`、`execution/` |
| QC & Critic | Q20/Q30、CheckM2 HQ、unclassified | `validators/bio_qc.py`、`agents/critic_agent.py` |
| Reporter | 多样性/通路叙述 + 表绑定解读 | `agents/reporter_agent.py`、`knowledge/grounded_interp.py` |
| HITL | 关键门控、CLI/API 审批 | `agents/hitl*.py`、`api/server.py` |

## Human-in-the-Loop

| 门控 | 时机 | 选项 |
|------|------|------|
| Assembly 算力 | 规划导出 / 执行前 | 提交 · MEGAHIT · 跳过 |
| OTU/ASV 低频 | 规划导出 / 统计前 | 均衡 / 严格 / 宽松 / 不剔除 |
| 参考库路径 | 非 mock 且 `paths.*` 缺失 | 就绪 · 部分库 · 中止 |
| 报告外发 | 规划导出 | 可分享 · 内部草稿 · 暂缓 |

- **sync**：Rich Prompt（`hitl.mode: sync`，生产建议 `auto_confirm: false`）
- **async**：写 `outdir/hitl/async/`，图路由到 `awaiting_hitl`→END；API `hitl_mode=async` + `GET/POST /runs/{id}/hitl`
- 审计：`hitl/critical_gates.json`

## Methods 要点

- 生物学推理层匹配场景 CoT，规划前须引用社区来源（nf-core / BioStars / 工具手册 RAG）
- Tool Specialist 绑定 Skill I/O 契约；引擎参数经 Pydantic Schema 写入 `workflow/params.yaml`（非自由 shell）
- 步骤缓存与 assembly checkpoint 支持续跑；可选 Nextflow `-resume` / Snakemake `--rerun-incomplete`
- 解读抗幻觉：物种 / p / q / effect 须来自 biomarkers 等程序表（`require_evidence_chain`）
- `mock` 仅用于 CI，不作为生物学真相

## Knowledge / 审计

- Hybrid RAG：`rag.mode=hybrid`；目录契约见 `database/README.md`
- 推理链：`outdir/reasoning/chain.md`
- 文献报告：`literature_report.md`；Chat：`POST /chat`

## 局限

全量 CAMI 基准、向量化项目 Memory、完整 Web UI 仍为部分能力。
