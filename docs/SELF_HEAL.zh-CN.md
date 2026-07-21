> English: [SELF_HEAL.md](SELF_HEAL.md)

# 自愈可靠性：假阳性与人工监督

面向手稿 / 技术读者：自动化“自我纠正”何时可能**误纠正**，以及 HITL 如何阻断高风险坏修复。

配套评估：`metagenomic_agent.evaluation.self_heal_fpr`（`pytest tests/test_self_heal_fpr.py`）。

---

## 1. 循环在图中的位置

```
execute_swarm → validate → hitl_runtime
  → (failure and retry_count < max_retries) → self_heal → execute_swarm
  → (analyst rejects heal) → critic …
critic fails and keywords match → self_heal
pi_replan → self_heal
```

实现：`execution/self_heal.py`、`graph._self_heal` / `_route_after_*`。  
自愈**仅修改** YAML/JSON 参数与 DAG；不重写自由形式 shell。

---

## 2. 风险分级（误修复如何损害结论）

| Risk | Action | Biological impact |
|------|--------|-------------------|
| High | `switch_to_mock_fallback` | 流水线“成功”但结果无生物学意义 |
| High | `loosen_qc` | 放宽 QC → 保留低质量 reads；丰度/差异可能偏倚 |
| High | `lower_kraken_confidence` | 掩盖污染或库错误；假阳性物种 ↑ |
| High | `downgrade_assembler` | MAG 完整性/断点变化；下游分箱结论可能偏移 |
| Medium | `increase_memory` / `reduce_threads` / `switch_to_container` / `pin_platform_amd64` | 资源与平台；通常不改生物学阈值 |
| Medium | `switch_taxonomy_tool` / `fix_db_path` | 工具/路径；需审计，但优于静默降低阈值 |

常量：`HIGH_RISK_ACTIONS`（代码与评估共用）。

---

## 3. 已知“误修复”模式（案例目录）

| Scenario ID | Erroneous correction | Current mitigation |
|-------------|----------------------|--------------------|
| `oom_taxonomy` | 任意 OOM 也曾提出 `downgrade_assembler` | **节点范围**：仅对组装相关 OOM/SPAdes 降级 |
| `soft_qc_warning` | Critic 文本含 `quality` 即触发 `loosen_qc` | 关键词收紧为 `fastp`/`phred`/`q30`/…（去掉裸 `quality`） |
| `pi_replan` | PI 重规划强制 `loosen_qc` | 仅保留 `switch_taxonomy_tool` |
| `missing_binary` | 自动 `switch_to_mock_fallback` | 标为高风险；默认 HITL **B=仅安全动作** 会扣留 |
| `bio_fail_confidence` | 生物校验失败 → 降低 Kraken 置信度 | 高风险；默认不自动应用 |

完整场景与评分：`evaluation/self_heal_fpr.catalog()`。

---

## 4. 假阳性率（FPR）定义与基线

在固定场景套件上（不可外推至临床队列）：

| Metric | Definition | Target |
|--------|------------|--------|
| **Trigger FPR** | P(进入 heal \| 金标准不应 heal) | → 0 |
| **Action FPR** | P(场景提出 ≥1 个 `forbidden` 动作) | 宜低；“提出但扣留”允许 |
| **Action FPR @ safe policy** | `filter_actions_for_policy(approve_high_risk=False)` 后仍应用 forbidden | **必须为 0** |

复现：

```bash
python -c "from metagenomic_agent.evaluation.self_heal_fpr import evaluate_self_heal_fpr; \
from pprint import pprint; pprint(evaluate_self_heal_fpr())"
pytest -q tests/test_self_heal_fpr.py
```

建议手稿表述：报告场景套件规模、Trigger FPR，以及**安全策略下 Action FPR=0**；说明高风险动作默认不自动应用。

---

## 5. 人工复核环（阻断错误纠正）

配置（`config/default.yaml`）：

```yaml
hitl:
  require_self_heal_confirm: true   # enable gate when high-risk actions are present
  default_self_heal: B              # A=all  B=safe only (recommended)  C=reject heal
```

门控 ID：`confirm_self_heal`（`hitl_gates.build_self_heal_gate`）。

| Option | Behavior |
|--------|----------|
| A `approve_all_heal` | 应用全部提案（含高风险） |
| B `approve_safe_heal_only` | 仅应用低/中风险；高风险写入 `self_heal_withheld` |
| C `reject_heal` | 不改 DAG；`self_heal_skipped` → 路由至 **critic**（保留原错误） |

审计字段（写入 `artifacts` / 报告 Methods）：`self_heal_proposed`、`self_heal_actions`、`self_heal_withheld`、`self_heal_decision`、`self_heal_risk`。

生产建议：

1. 保持 `require_self_heal_confirm: true` 与 `default_self_heal: B`。  
2. 交互式 CLI：关闭 `hitl.auto_confirm`；由生信人员显式选择 A/B/C。  
3. 主手稿结果勿依赖 `switch_to_mock_fallback`；`sandbox.allow_mock_fallback` 仅用于工程冒烟测试。  
4. 报告 Methods 须列出已应用的 `self_heal_actions` 与扣留项。

---

## 6. 与“正确”自愈的边界

仍鼓励自动执行（在 `max_retries` 内）：

- 内存 / 线程 / 超时调整  
- 切换至 Docker / 钉死 `linux/amd64`  
- 提示 `fix_db_path`，或在库缺失时追加 MetaPhlAn  

这些动作会审计，但默认不请求 HITL（除非与高风险项捆绑）。

---

## 7. 局限（诚实的手稿小节）

- 当前 FPR 来自**合成场景回归**，非大规模真实失败日志的流行病学估计。  
- Critic→heal 仍依赖关键词，可能漏检（FN）真正需要重跑的案例。  
- 即使 HITL 批准 `lower_kraken_confidence`，污染仍可能被掩盖——应优先做宿主过滤与参考库检查。  
- 扩充真实 stderr 语料后，重新运行 `evaluate_self_heal_fpr` 并更新本节数字。
