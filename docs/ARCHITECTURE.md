# 架构说明

面向 **v0.14**。详见 [USAGE.md](USAGE.md)、[ROADMAP.md](ROADMAP.md)。

## 设计

```
User → Router → Bio Reasoning (CoT + nf-core/BioStars citations + audit)
     → Supervisor → Tool Specialist (skill I/O contracts, not free-form shell)
     → resource estimate → HITL → Swarm + step cache
     → interpretation → lite dashboard → report
```

| 主题 | 路径 |
|------|------|
| 技能契约 | `skills/contracts.py` · `skills/registry.py` · `tool_specialist.py` |
| 步骤缓存 | `execution/step_cache.py` |
| 资源预估 | `execution/resource_estimate.py` |
| CoT 推理 | `knowledge/bio_cot_examples.json` · `bio_reasoning_agent.py` |
| 轻量可视化 | `report/interactive.py`（`visualization.lite`） |
| 引擎 resume | `execution/engine.py`（nf `-resume` / smk `--rerun-incomplete`） |

```
parse → router → bio_reasoning → supervisor → tool_specialist → plan_validator
  → export_dag(+resource_estimate) → workflow_agent → contract → HITL
  → swarm(cache) → validate → quality → HITL(runtime) → …
  → visualization → xai → report
```
