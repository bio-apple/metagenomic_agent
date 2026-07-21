# 顶刊导向优化实施说明（对应优化建议书）

本文档记录建议书三阶段在代码中的落地位置。

## 第一阶段：技能与契约

| 组件 | 路径 |
|------|------|
| Input/Output Contract | `src/metagenomic_agent/skills/contracts.py` |
| Skill 注册表 | `src/metagenomic_agent/skills/registry.py` |
| 标准剧本 Playbook | `src/metagenomic_agent/skills/playbooks.py` |
| 契约检查节点 | `src/metagenomic_agent/skills/checker.py` → 图节点 `contract_check` |

主链路：`supervisor → contract_check → hitl → execute_swarm → …`

## 第二阶段：gLM 与智能路由

| 组件 | 路径 |
|------|------|
| microCafe / MicroRAG 适配 | `src/metagenomic_agent/tools/glm.py` |
| 读长路由 + 双路融合 | `src/metagenomic_agent/skills/router.py` |
| Epsilon-Greedy 工具档案 | `src/metagenomic_agent/skills/bandit.py` |
| Taxonomy Agent 集成 | `src/metagenomic_agent/agents/taxonomy_agent.py` |

长读长（≥5000 bp）优先 `microcafe`；短读长默认经典工具，可 dual-path 融合。

## 第三阶段：生物学验证与可复现

| 组件 | 路径 |
|------|------|
| IBD/健康/肿瘤标志物 KB | `src/metagenomic_agent/knowledge/ibd_biomarker_kb.json` |
| 上下文感知验证 | `src/metagenomic_agent/validators/biological.py` |
| CWL + run_manifest | `src/metagenomic_agent/report/reproducibility.py` → `results/reproducibility/` |

## 配置

见 `config/default.yaml` 中 `routing:` 段。
