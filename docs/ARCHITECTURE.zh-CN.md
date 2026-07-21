> English: [ARCHITECTURE.md](ARCHITECTURE.md)

# 架构与设计（v0.24）

定位：**面向微生物组发现的自主 AI 科学家**（宏基因组研究 Agent，而非薄封装流水线包装器）。

配套文档：[USAGE.zh-CN.md](USAGE.zh-CN.md)（用法）· [DEPLOY_LINUX.zh-CN.md](DEPLOY_LINUX.zh-CN.md)（≥256 GB 部署）· [database/README.zh-CN.md](../database/README.zh-CN.md)（参考数据库）· [SELF_HEAL.zh-CN.md](SELF_HEAL.zh-CN.md)（自愈 FPR / HITL）。

## 目标

理解研究问题 → 规划分析 → 调用生物信息工具 → 解读结果 → 以文献/KG 落地 → 自评与纠错 → 产出可重复报告。

**范围**：宏基因组学（shotgun / 16S 相关工作流）。不做多组学扩展。

**项目语言**：文档、CLI/Web UI、HITL 提示与报告均为**英文**。可选中文 token 仅作为路由器/知识触发中的查询匹配别名，使非英文研究问题仍能正确路由。

## 编排主干

图摘要（仓库 README）：[`docs/figures/overview.svg`](figures/overview.svg)。

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → planner → export_dag(+HITL) → workflow → contract → HITL
  → executor swarm (QC · Taxonomy · Function · Resistance · Stats · Assembly…)
  → validate → [self_heal ↻ swarm] → critic → [scientific_replan ↻ swarm] → literature → evidence → reviewer → reflection
  → pi_review → [scientific_replan ↻ swarm] → viz → code_agent → reporter → xai → report(+MetaAgentScore)
```

`self_heal`：分类错误 → 提出动作 → **高风险需 HITL** → 更新参数/DAG → 重跑 swarm（`max_retries`，默认 2）。详情：[SELF_HEAL.zh-CN.md](SELF_HEAL.zh-CN.md)。

`scientific_replan`：当 Critic/PI 结论暗示工具或流程重设计（分类/MAG/统计）时，修补 DAG + 配置并重新进入 `execute_swarm`（受 `max_scientific_replan` 限制，默认 1）。与仅资源级的 self-heal 区分。

异步 HITL：`resume_pipeline` 从 `execute_swarm` 继续。

## Agent 概览

| Agent | Responsibility | Path |
|-------|----------------|------|
| Planner | 研究问题 → 分析计划 | `agents/planner_agent.py` |
| QC | fastp / MultiQC 风格打分 | `agents/qc_agent.py` |
| Taxonomy | Kraken2 / Bracken / MetaPhlAn / Centrifuge | `agents/taxonomy_agent.py` |
| Function | DIAMOND / KEGG / HUMAnN | `agents/function_agent.py` |
| Resistance | CARD/RGI / DeepARG / ResFinder / VFDB | `agents/resistance_agent.py` |
| Statistics | Alpha/Beta / 差异 / R 导出 | `agents/statistics_agent.py` |
| Literature | PubMed + RAG | `agents/literature_agent.py` |
| Evidence | 统计 + 文献 + KG | `agents/evidence_agent.py` |
| Reviewer | 同行评议风格的置信度/关切 | `agents/reviewer_agent.py` |
| Reflection | ReAct Observe→Correct | `agents/reflection_agent.py` |
| Code | 沙箱 Python 表分析 | `agents/code_agent.py` |
| Reporter / Report | 解读与 HTML/手稿 | `agents/reporter_agent.py`, `report/` |
| Executor | HPC / 容器 / swarm | `agents/executor_agent.py` |

## 知识与抗幻觉

- 混合 RAG（`rag.mode=hybrid`）+ 微生物组 KG（`knowledge/microbiome_kg.py`）
- 完整参考库构建：见 [database/README.md](../database/README.md)（Kraken2 / MetaPhlAn / GTDB / CARD…）
- 表绑定：`require_evidence_chain`（物种/p/q/效应来自程序表）
- 推理审计：`outdir/reasoning/chain.md`
- 项目 Memory：`ContextMemory.retrieve`（TF-IDF）

## 人在回路（Human-in-the-Loop）

| Gate | Options |
|------|---------|
| 组装算力 | Submit · MEGAHIT · Skip |
| 稀有 OTU/ASV | Balanced / Strict / Lenient / None |
| 参考库路径 | Ready · Partial · Abort |
| **自愈高风险** | Approve all · **Safe only（默认）** · Reject heal |
| 报告发布 | Shareable · Draft · Hold |

`hitl.mode`：`sync`（CLI）\| `async`（API `/runs/{id}/hitl`）。

## 工作流与部署

- 引擎：LangGraph（默认）· Nextflow · Snakemake；参数在 `workflow/params.yaml`
- 容器：Docker / Apptainer（BioContainers）；编排见 `Dockerfile` / `docker-compose.yml`
- HPC：SLURM / PBS / SGE；大内存配置见 [DEPLOY_LINUX.zh-CN.md](DEPLOY_LINUX.zh-CN.md)
- UI：`GET /ui` · Chat：`POST /chat`

## 评估

| Item | Description |
|------|-------------|
| MetaAgentScore | Planning / Tool / Execution / Reasoning / Error / Repro |
| CAMI toy | 属水平 P/R/F1（CI 回归；非完整 OPAMI） |
| Functional closure | 上表全部 Agent 均已实现 |

## 方法要点

- 规划前引用社区来源（nf-core / BioStars / 工具手册）
- Skill 契约 + Pydantic Schema；无自由形式 shell
- Checkpoint / 步骤缓存；`mock` 仅用于 CI
