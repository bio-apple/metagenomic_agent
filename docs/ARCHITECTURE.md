# 架构说明（v0.23）

CLI / 配置见 [USAGE.md](USAGE.md)；设计全文见 [DESIGN.md](DESIGN.md)；闭环对照见 [OPTIMIZATION.md](OPTIMIZATION.md)。

## 编排主链

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → planner → export_dag(+HITL) → workflow → contract → HITL
  → executor swarm (QC · Taxonomy · Function · Resistance · Stats · Assembly…)
  → validate → critic → literature → evidence → reviewer → reflection
  → pi_review → viz → code_agent → reporter → xai → report(+MetaAgentScore)
```

## 角色与模块

| 角色 | 职责 | 主要路径 |
|------|------|----------|
| Planner | 科研问题 → 分析计划 | `agents/planner_agent.py` |
| QC | fastp/MultiQC 风格评分 | `agents/qc_agent.py` |
| Taxonomy | Kraken2/Bracken/MetaPhlAn/Centrifuge | `agents/taxonomy_agent.py` |
| Function | HUMAnN/DIAMOND/KEGG | `agents/function_agent.py` |
| Resistance | CARD/RGI/DeepARG/ResFinder/VFDB | `agents/resistance_agent.py` |
| Evidence | 统计+文献+KG 整合 | `agents/evidence_agent.py` |
| Reviewer | 审稿式 confidence/concerns | `agents/reviewer_agent.py` |
| Reflection | ReAct Observe→Correct | `agents/reflection_agent.py` |
| Code | 沙箱 Python 表分析 | `agents/code_agent.py` |
| KG | Microbe–Pathway–Disease–PMID | `knowledge/microbiome_kg.py` |

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

## 评估 / Memory / UI

- CAMI toy：`evaluation/cami_toy`（属级 P/R/F1；非全量 OPAMI）
- Memory：`ContextMemory.retrieve`（本地 TF-IDF）
- Web UI：`GET /ui`；期刊 R 脚本：`biomarkers/r_export/`
