# 架构与设计（v0.23）

定位：**Autonomous AI Scientist for Microbiome Discovery**（宏基因组科研智能体，非简单 pipeline wrapper）。

配套：[USAGE.md](USAGE.md)（用法）· [DEPLOY_LINUX.md](DEPLOY_LINUX.md)（≥256 GB 部署）· [database/README.md](../database/README.md)（参考库）· [SELF_HEAL.md](SELF_HEAL.md)（自愈 FPR / HITL）。

## 目标

理解科研问题 → 规划分析 → 调用生信工具 → 解释结果 → 文献/KG 接地 → 自我评价与修正 → 可复现报告。

**范围**：宏基因组（shotgun / 16S 相关流程）。不做多组学扩展。

## 编排主链

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → planner → export_dag(+HITL) → workflow → contract → HITL
  → executor swarm (QC · Taxonomy · Function · Resistance · Stats · Assembly…)
  → validate → [self_heal ↻ swarm] → critic → literature → evidence → reviewer → reflection
  → pi_review → viz → code_agent → reporter → xai → report(+MetaAgentScore)
```

`self_heal`：错误分类 → 提议动作 → **高风险需 HITL** → 改参数/DAG → 重跑 swarm（`max_retries`，默认 2）。详见 [SELF_HEAL.md](SELF_HEAL.md)。

异步 HITL：`resume_pipeline` 从 `execute_swarm` 续跑。

## Agent 一览

| Agent | 职责 | 路径 |
|-------|------|------|
| Planner | 科研问题 → 分析计划 | `agents/planner_agent.py` |
| QC | fastp / MultiQC 风格评分 | `agents/qc_agent.py` |
| Taxonomy | Kraken2 / Bracken / MetaPhlAn / Centrifuge | `agents/taxonomy_agent.py` |
| Function | DIAMOND / KEGG / HUMAnN | `agents/function_agent.py` |
| Resistance | CARD/RGI / DeepARG / ResFinder / VFDB | `agents/resistance_agent.py` |
| Statistics | Alpha/Beta / 差异 / R 导出 | `agents/statistics_agent.py` |
| Literature | PubMed + RAG | `agents/literature_agent.py` |
| Evidence | 统计+文献+KG | `agents/evidence_agent.py` |
| Reviewer | 审稿式 confidence/concerns | `agents/reviewer_agent.py` |
| Reflection | ReAct Observe→Correct | `agents/reflection_agent.py` |
| Code | 沙箱 Python 表分析 | `agents/code_agent.py` |
| Reporter / Report | 解读与 HTML/手稿 | `agents/reporter_agent.py`、`report/` |
| Executor | HPC / 容器 / swarm | `agents/executor_agent.py` |

## 知识与抗幻觉

- Hybrid RAG（`rag.mode=hybrid`）+ Microbiome KG（`knowledge/microbiome_kg.py`）
- 全量参考库构建：见 [database/README.md](../database/README.md)（Kraken2 / MetaPhlAn / GTDB / CARD…）
- 表绑定：`require_evidence_chain`（物种/p/q/effect 来自程序表）
- 推理审计：`outdir/reasoning/chain.md`
- 项目 Memory：`ContextMemory.retrieve`（TF-IDF）

## Human-in-the-Loop

| 门控 | 选项 |
|------|------|
| Assembly 算力 | 提交 · MEGAHIT · 跳过 |
| OTU/ASV 低频 | 均衡 / 严格 / 宽松 / 不剔除 |
| 参考库路径 | 就绪 · 部分 · 中止 |
| **Self-Heal 高风险** | 全部批准 · **仅安全（默认）** · 拒绝自愈 |
| 报告外发 | 可分享 · 草稿 · 暂缓 |

`hitl.mode`: `sync`（CLI）\| `async`（API `/runs/{id}/hitl`）。

## 工作流与部署

- 引擎：LangGraph（默认）· Nextflow · Snakemake；参数 `workflow/params.yaml`
- 容器：Docker / Apptainer（BioContainers）；编排层 `Dockerfile` / `docker-compose.yml`
- HPC：SLURM / PBS / SGE；大内存配置见 [DEPLOY_LINUX.md](DEPLOY_LINUX.md)
- UI：`GET /ui` · Chat：`POST /chat`

## 评估

| 项 | 说明 |
|----|------|
| MetaAgentScore | Planning / Tool / Execution / Reasoning / Error / Repro |
| CAMI toy | 属级 P/R/F1（CI 回归，非全量 OPAMI） |
| 功能闭环 | 上表 Agent 均已落地 |

## Methods 要点

- 规划前引用社区来源（nf-core / BioStars / 工具手册）
- Skill 契约 + Pydantic Schema，禁止自由 shell
- Checkpoint / step cache；`mock` 仅用于 CI
