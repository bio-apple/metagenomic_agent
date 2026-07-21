# 顶刊导向优化实施说明

对应建议书：[Optimization_Proposal_IF10.md](Optimization_Proposal_IF10.md)  
状态：**v0.5.0 已完成三阶段 MVP**（契约 / gLM 路由 / 生物学验证 + CWL）。

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

长读长（≥5000 bp）优先 `microcafe`；短读长默认经典工具，可 dual-path 融合。配置见 `config/default.yaml` → `routing:`。

## 第三阶段：生物学验证与可复现

| 组件 | 路径 |
|------|------|
| IBD/健康/肿瘤标志物 KB | `src/metagenomic_agent/knowledge/ibd_biomarker_kb.json` |
| 上下文感知验证 | `src/metagenomic_agent/validators/biological.py` |
| CWL + run_manifest | `src/metagenomic_agent/report/reproducibility.py` → `results/reproducibility/` |

## 测试与文档

- 契约/路由/生物警告：`tests/test_skills_contracts.py`
- 端到端产物断言：`tests/test_graph_dryrun.py`（含 `contract_check.json`、`meta_agent.cwl`）
- 架构与用法：[ARCHITECTURE.md](ARCHITECTURE.md)、[USAGE.md](USAGE.md)

## 尚未纳入本 MVP（后续）

- 真实 gLM 权重与 GPU 推理服务绑定
- 长读长公开数据集的正式基准报告
- 契约硬失败默认中止（当前可走 HITL / Critic 警告路径）
