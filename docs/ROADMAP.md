# 开发者路线图（对照建议）

对照「宏基因组生物信息 Agent 开发者建议」与当前 **v0.13** 实现。状态：`Done` / `Partial` / `Planned`。

## 目标架构

```
User → Requirement Understanding → Biological Reasoning
     → Workflow Planning → Tool Execution → Result Interpretation
     → Scientific Report
```

| 建议能力 | 状态 | 现状 |
|----------|------|------|
| 1. Bio Reasoning（规划前） | **Done** | `agents/bio_reasoning_agent.py`；图：`router → bio_reasoning → supervisor` |
| 2. Multi-Agent / PM | **Done** | Supervisor 任务分解；QC/Tax/Asm/Function/Stats/Critic/Literature/Viz/Report |
| 2.2 FastQC/MultiQC | Partial | 主路径 fastp；FastQC/MultiQC 待接 |
| 2.3 Taxonomy 生物学解释 | **Done** | `taxonomy_interpretation.md`（污染 vs 富集假设） |
| 2.4 组装复杂度选工具 | **Done** | Bio Reasoning → `assembler_preference`；高复杂 MEGAHIT |
| 2.5 Functional 机制解读 | **Done** | `functional_interpretation.md` + KEGG/CARD/UniProt RAG |
| 2.6 Publication Agent | Partial | `report/manuscript.py` 分节草稿（非独立图节点） |
| 3. Memory | Partial | `ContextMemory` + project/bio_reasoning 历史；向量库（Chroma/FAISS）Planned |
| 4. RAG 知识库 | Partial | curated 生物库 + 工具 domain KB + 文献 API；工具全文向量索引 Planned |
| 5. Benchmark（CAMI/HMP） | Partial | `evaluation/benchmarks.py` smoke；标准 CAMI 套件 Planned |
| 6. HITL 多方案 | **Done** | A/B/C 结构化选项（研究设计 / 缺分组 / 宿主污染） |
| 7. Conversation Agent | Partial | CLI/API 入口；多轮对话会话 Planned |
| 8.1 自主流程优化 | Partial | self-heal + bandit 路由；完整 observe→optimize 环 Planned |
| 8.2 Biological Reasoning（机制/下一步实验） | **Done** | 规划前推理 + 证据链 + next_experiments |
| 8.3 Reproducible Science Agent | **Done** | Docker/沙盒、`.nf`/`.smk`、seed、Methods、manifest |

## 图节点（v0.13）

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → export_dag → workflow_agent → contract → HITL
  → swarm → validate → quality → HITL(runtime) → self-heal*
  → critic → literature → PI* → visualization → XAI → report
```

## 近期优先（Planned）

1. FastQC/MultiQC 与 HUMAnN3 原生封装  
2. 项目级向量 Memory（FAISS/Chroma）跨 run 检索  
3. CAMI II / HMP 基准脚本与 CI 指标看板  
4. 独立 Conversation Agent（多轮澄清需求）  
5. Publication Agent 升为图节点（Methods/Results/Figures 一键打包）

最终目标保持不变：**Autonomous Multi-Agent System for End-to-End Metagenomic Discovery**。
