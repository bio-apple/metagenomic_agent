# 架构说明

面向 **v0.19**。详见 [USAGE.md](USAGE.md)、[ROADMAP.md](ROADMAP.md)。

## Human-in-the-Loop

关键节点需生信人员确认后再继续：

| 触发点 | 时机 | 选项 |
|--------|------|------|
| **Assembly 算力** | 规划导出 / 执行前 | 确认提交 · 改 MEGAHIT · 跳过 |
| **OTU/ASV 低频剔除** | 规划导出 / 统计前 | 均衡/严格/宽松/不剔除 |

```
… → export_dag（注册 critical gates）→ HITL 确认
  → Executor → [再确认 Assembly] → … → [再确认 OTU 阈值] → Statistics
```

| 模块 | 路径 |
|------|------|
| 门控定义 | `agents/hitl_gates.py` |
| 动作应用 | `agents/hitl.py` |
| 审计 | `hitl/critical_gates.json` |
| 过滤执行 | `statistics` → `diversity_analysis/otu_asv_filter.json` |

交互生产：`hitl.auto_confirm: false`（CLI 不加 `--yes`）。
