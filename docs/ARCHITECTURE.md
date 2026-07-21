# 架构说明

面向 **v0.18**。详见 [USAGE.md](USAGE.md)、[ROADMAP.md](ROADMAP.md)。

## 设计

```
… → Executor → QC & Critic（bio QC 链）
     → Literature → Reporter（表绑定解读）→ Report
```

| 主题 | 路径 |
|------|------|
| CheckM2 / 分类率 QC 链 | `validators/bio_qc.py` → `critic/bio_qc_chain.json` |
| High-quality MAG 门控 | Completeness ≥90% · Contamination ≤5% |
| Unclassified 过高 | 提示换库 / 提高 Kraken2 confidence |
| 幻觉护栏 | `knowledge/grounded_interp.py`：物种/p/q/effect 必须来自 biomarkers·LEfSe 表 |
| 证据链 | `evidence_chain.py` + `interpretation.require_evidence_chain` |

High-quality MAG 与 taxonomy unclassified 在 Critic / technical validator 共用同一阈值源（`config.validation`）。
