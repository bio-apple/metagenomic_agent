# 架构说明（v0.7）

源码根目录：`src/metagenomic_agent/`。

## 分层

```text
┌──────────────────────────────────────────────────────────────┐
│  CLI (meta-agent) · FastAPI (/analyze)                       │
├──────────────────────────────────────────────────────────────┤
│  LangGraph (graph.py)                                        │
│  parse → supervisor → export_dag → contract_check → HITL     │
│       → swarm → validate → quality → self-heal*              │
│       → critic → literature → pi_review* → viz → report      │
├─────────────┬────────────────────┬───────────────────────────┤
│ Agents      │ Skills / RAG       │ Tools / Stats             │
│ supervisor  │ contracts/playbook │ fastp, kraken, glm…       │
│ qc/tax/asm  │ router, bandit     │ ToolContext modes         │
│ stats/crit  │ rag/* + TF-IDF     │ ordination, lefse_like…   │
│ lit/PI/viz  │ decision           │ linux/docker runners      │
├─────────────┴────────────────────┴───────────────────────────┤
│ Validators · Knowledge · Report/CWL/Manuscript · Benchmarks  │
└──────────────────────────────────────────────────────────────┘
```

## 图节点

| 节点 | 模块 | 职责 |
|------|------|------|
| `parse_input` | `input/parser.py` | 样本与读长特征 |
| `supervisor` | `agents/supervisor.py` | 规划 + project Memory |
| `export_dag` | `execution/dag_export.py` | `workflow/dag.json` |
| `contract_check` | `skills/checker.py` | 前置契约；可选硬失败 |
| `hitl` | `agents/hitl.py` | 人机确认 |
| `execute_swarm` | `execution/executor.py` | 拓扑调度专用 Agent |
| `validate` | `validators/loop.py` | 技术 + 生物学验证 |
| `quality_scores` | `evaluation/quality_score.py` | 综合质量分 |
| `self_heal` | `execution/self_heal.py` | 降参 / 换工具重试 |
| `critic` | `agents/critic_agent.py` | 警告汇总 |
| `literature` | `agents/literature_agent.py` | 文献 + Evidence Table + bio-RAG |
| `pi_review` | `agents/pi_agent.py` | PI 复盘，可触发再跑 |
| `visualization` | `agents/visualization_agent.py` | PCoA / 共现 / Volcano 等 |
| `report` | `report/generator.py` | HTML + methods + manuscript + CWL |

## 能力清单（相对建议书）

| 能力 | 位置 |
|------|------|
| Skill / Contract / Playbook | `skills/` |
| gLM 路由 + ε-greedy | `skills/router.py`, `bandit.py`, `tools/glm.py` |
| 生物库 RAG | `rag/`（gtdb/card/vfdb/kegg/mgnify/bacdive/hmp/refseq/ncbi/eggnog） |
| TF-IDF 语义检索 | `rag/embeddings.py` |
| Evidence Table | `agents/evidence.py` → `evidence/` |
| PCoA / 共现 / LEfSe-like / ANCOM-like | `stats/` |
| 质量评分 | `evaluation/quality_score.py` |
| 手稿草稿 | `report/manuscript.py` |
| 契约硬失败 | `validation.contract_hard_fail` |
| gLM 外部推理 | `paths.glm_inference_cmd` |
| Benchmark | `evaluation/benchmarks.py` |
| Snakemake / Nextflow | `workflow/` |

## 包结构

```text
agents/          # 专用智能体（含 PI、visualization）
skills/          # 契约、剧本、路由、决策
rag/             # 生物数据库检索
stats/           # 排序、差异近似、共现
tools/           # 生信与 gLM
validators/      # 技术 + 生物学
execution/       # 调度、DAG 导出、自愈、监控
report/          # 报告、手稿、CWL
knowledge/       # gut/IBD KB、best_practices
evaluation/      # metrics、quality、benchmarks
coordinator/     # Memory、环境探测
api/             # FastAPI
```

## 设计原则

1. **Mock 可测**：无 GPU/全库也可跑通 CI。  
2. **诚实披露**：近似统计与 curated RAG 在 Methods 中标明。  
3. **可移交**：DAG JSON + CWL + reproduce.sh 支持外部引擎。  
4. **可扩展**：全量 DB / 真实 gLM 通过 paths 挂载，不改编排主链。
