# Self-Heal 可靠性：假阳性与人审防呆

面向论文 / 技术文档读者：自动化「自我纠错」何时会**纠错**，以及如何用 HITL 拦住高风险误修。

配套可运行评估：`metagenomic_agent.evaluation.self_heal_fpr`（`pytest tests/test_self_heal_fpr.py`）。

---

## 1. 闭环在图中的位置

```
execute_swarm → validate → hitl_runtime
  → (失败且 retry_count < max_retries) → self_heal → execute_swarm
  → (分析员拒绝自愈) → critic …
critic 未通过且关键词命中 → self_heal
pi_replan → self_heal
```

实现：`execution/self_heal.py`、`graph._self_heal` / `_route_after_*`。  
自愈**只改** YAML/JSON 参数与 DAG，不重写自由 shell。

---

## 2. 风险分级（误修如何伤害结论）

| 风险 | 动作 | 生物学影响 |
|------|------|------------|
| 高 | `switch_to_mock_fallback` | 流程「成功」但结果无生物学意义 |
| 高 | `loosen_qc` | 放宽质控 → 保留低质量读段，丰度/差异可偏 |
| 高 | `lower_kraken_confidence` | 掩盖污染或库错误，假阳性物种↑ |
| 高 | `downgrade_assembler` | MAG 完整性/断点变化，下游 binning 结论可变 |
| 中 | `increase_memory` / `reduce_threads` / `switch_to_container` / `pin_platform_amd64` | 资源与平台；一般不改生物学阈值 |
| 中 | `switch_taxonomy_tool` / `fix_db_path` | 工具/路径；需审计但仍优于静默降阈值 |

常量：`HIGH_RISK_ACTIONS`（代码与评估共用）。

---

## 3. 已知会「纠错」的模式（案例库）

| 场景 ID | 错误纠正 | 现况缓解 |
|---------|----------|----------|
| `oom_taxonomy` | 任意 OOM 曾附带 `downgrade_assembler` | **节点作用域**：仅 assembly 相关 OOM/SPAdes 才降级 |
| `soft_qc_warning` | Critic 文案含 `quality` 即触发 `loosen_qc` | 关键词收紧为 `fastp`/`phred`/`q30`/…（去掉裸 `quality`） |
| `pi_replan` | PI 重规划强制 `loosen_qc` | 仅保留 `switch_taxonomy_tool` |
| `missing_binary` | 自动 `switch_to_mock_fallback` | 列为高风险；默认 HITL **B=仅安全动作** 暂缓 |
| `bio_fail_confidence` | 生物校验失败 → 降 Kraken confidence | 高风险；默认不自动应用 |

完整场景与评分：`evaluation/self_heal_fpr.catalog()`。

---

## 4. 假阳性率（FPR）定义与基准结果

在固定场景集上（非临床队列外推）：

| 指标 | 定义 | 目标 |
|------|------|------|
| **Trigger FPR** | P(进入 heal \| 金标准不应 heal) | → 0 |
| **Action FPR** | P(场景提出 ≥1 个 `forbidden` 动作) | 尽量低；允许「提出但暂缓」 |
| **Action FPR @ safe policy** | 经 `filter_actions_for_policy(approve_high_risk=False)` 后仍应用 forbidden | **必须为 0** |

复现：

```bash
python -c "from metagenomic_agent.evaluation.self_heal_fpr import evaluate_self_heal_fpr; \
from pprint import pprint; pprint(evaluate_self_heal_fpr())"
pytest -q tests/test_self_heal_fpr.py
```

投稿表述建议：报告场景集规模、Trigger FPR、以及 **safe-policy 后 Action FPR=0**；并声明高风险动作默认不自动落地。

---

## 5. 人审循环（如何防止错误纠正）

配置（`config/default.yaml`）：

```yaml
hitl:
  require_self_heal_confirm: true   # 存在高风险动作时启用门控
  default_self_heal: B              # A=全部  B=仅安全（推荐）  C=拒绝自愈
```

门控 ID：`confirm_self_heal`（`hitl_gates.build_self_heal_gate`）。

| 选项 | 行为 |
|------|------|
| A `approve_all_heal` | 应用含高风险在内的全部提议 |
| B `approve_safe_heal_only` | 只应用低/中风险；高风险写入 `self_heal_withheld` |
| C `reject_heal` | 不改 DAG；`self_heal_skipped` → 路由到 **critic**（保留原错误） |

审计字段（写入 `artifacts` / 报告 Methods）：`self_heal_proposed`、`self_heal_actions`、`self_heal_withheld`、`self_heal_decision`、`self_heal_risk`。

生产建议：

1. 保持 `require_self_heal_confirm: true` 与 `default_self_heal: B`。  
2. CLI 交互：关闭 `hitl.auto_confirm`，由生信人员显式选 A/B/C。  
3. 禁止在论文主结果中依赖 `switch_to_mock_fallback`；`sandbox.allow_mock_fallback` 仅限工程冒烟。  
4. 报告 Methods 必须列出实际应用的 `self_heal_actions` 与暂缓项。

---

## 6. 与「正确自愈」的边界

仍鼓励自动执行的修复（在 max_retries 内）：

- 内存/线程/超时调整  
- 切 Docker / 钉 `linux/amd64`  
- 缺失库时提示 `fix_db_path`、追加 MetaPhlAn  

这些动作也写入审计，但不默认索要 HITL（除非同时夹带高风险项）。

---

## 7. 局限（论文诚实段）

- 当前 FPR 来自**合成场景回归**，不是大规模真实失败日志的流行病学估计。  
- Critic→heal 仍依赖关键词，可能漏报（FN）真实需重跑的情况。  
- `lower_kraken_confidence` 即使经 HITL 批准，仍可能掩盖污染——应优先查宿主过滤与参考库。  
- 扩展真实 stderr 语料后应重跑 `evaluate_self_heal_fpr` 并更新本节数字。
