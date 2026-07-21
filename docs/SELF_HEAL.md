# Self-Heal Reliability: False Positives and Human Oversight

For manuscript / technical readers: when automated “self-correction” can **mis-correct**, and how HITL blocks high-risk bad fixes.

Companion evaluation: `metagenomic_agent.evaluation.self_heal_fpr` (`pytest tests/test_self_heal_fpr.py`).

---

## 1. Where the loop sits in the graph

```
execute_swarm → validate → hitl_runtime
  → (failure and retry_count < max_retries) → self_heal → execute_swarm
  → (analyst rejects heal) → critic …
critic fails and keywords match → self_heal
pi_replan → self_heal
```

Implementation: `execution/self_heal.py`, `graph._self_heal` / `_route_after_*`.  
Self-heal **only mutates** YAML/JSON parameters and the DAG; it does not rewrite free-form shell.

---

## 2. Risk tiers (how mis-fixes harm conclusions)

| Risk | Action | Biological impact |
|------|--------|-------------------|
| High | `switch_to_mock_fallback` | Pipeline “succeeds” but results have no biological meaning |
| High | `loosen_qc` | Relaxed QC → retain low-quality reads; abundance/differential may bias |
| High | `lower_kraken_confidence` | Masks contamination or DB errors; false-positive species ↑ |
| High | `downgrade_assembler` | MAG completeness/breakpoints change; downstream binning conclusions may shift |
| Medium | `increase_memory` / `reduce_threads` / `switch_to_container` / `pin_platform_amd64` | Resources and platform; generally do not alter biological thresholds |
| Medium | `switch_taxonomy_tool` / `fix_db_path` | Tool/path; needs audit but preferred over silently lowering thresholds |

Constant: `HIGH_RISK_ACTIONS` (shared by code and evaluation).

---

## 3. Known “mis-fix” patterns (case catalog)

| Scenario ID | Erroneous correction | Current mitigation |
|-------------|----------------------|--------------------|
| `oom_taxonomy` | Any OOM previously also proposed `downgrade_assembler` | **Node scope**: downgrade only for assembly-related OOM/SPAdes |
| `soft_qc_warning` | Critic text containing `quality` triggered `loosen_qc` | Keywords tightened to `fastp`/`phred`/`q30`/… (bare `quality` removed) |
| `pi_replan` | PI replan forced `loosen_qc` | Keep only `switch_taxonomy_tool` |
| `missing_binary` | Auto `switch_to_mock_fallback` | Marked high-risk; default HITL **B=safe actions only** withholds it |
| `bio_fail_confidence` | Bio validation failure → lower Kraken confidence | High-risk; not applied automatically by default |

Full scenarios and scoring: `evaluation/self_heal_fpr.catalog()`.

---

## 4. False-positive rate (FPR) definition and baseline

On a fixed scenario suite (not extrapolatable to clinical cohorts):

| Metric | Definition | Target |
|--------|------------|--------|
| **Trigger FPR** | P(enter heal \| gold standard should not heal) | → 0 |
| **Action FPR** | P(scenario proposes ≥1 `forbidden` action) | Prefer low; “propose but withhold” is allowed |
| **Action FPR @ safe policy** | Forbidden still applied after `filter_actions_for_policy(approve_high_risk=False)` | **Must be 0** |

Reproduce:

```bash
python -c "from metagenomic_agent.evaluation.self_heal_fpr import evaluate_self_heal_fpr; \
from pprint import pprint; pprint(evaluate_self_heal_fpr())"
pytest -q tests/test_self_heal_fpr.py
```

Suggested manuscript wording: report scenario-suite size, Trigger FPR, and **Action FPR=0 under safe policy**; state that high-risk actions are not applied automatically by default.

---

## 5. Human review loop (blocking erroneous corrections)

Config (`config/default.yaml`):

```yaml
hitl:
  require_self_heal_confirm: true   # enable gate when high-risk actions are present
  default_self_heal: B              # A=all  B=safe only (recommended)  C=reject heal
```

Gate ID: `confirm_self_heal` (`hitl_gates.build_self_heal_gate`).

| Option | Behavior |
|--------|----------|
| A `approve_all_heal` | Apply all proposals including high-risk |
| B `approve_safe_heal_only` | Apply low/medium risk only; high-risk written to `self_heal_withheld` |
| C `reject_heal` | Do not change DAG; `self_heal_skipped` → route to **critic** (original error retained) |

Audit fields (written to `artifacts` / report Methods): `self_heal_proposed`, `self_heal_actions`, `self_heal_withheld`, `self_heal_decision`, `self_heal_risk`.

Production recommendations:

1. Keep `require_self_heal_confirm: true` and `default_self_heal: B`.  
2. Interactive CLI: disable `hitl.auto_confirm`; let bioinformaticians choose A/B/C explicitly.  
3. Do not rely on `switch_to_mock_fallback` in primary manuscript results; `sandbox.allow_mock_fallback` is for engineering smoke tests only.  
4. Report Methods must list applied `self_heal_actions` and withheld items.

---

## 6. Boundary with “correct” self-heal

Still encouraged for automatic execution (within `max_retries`):

- Memory / thread / timeout adjustments  
- Switch to Docker / pin `linux/amd64`  
- Prompt `fix_db_path` or append MetaPhlAn when DBs are missing  

These actions are audited but do not request HITL by default (unless bundled with high-risk items).

---

## 7. Limitations (honest manuscript section)

- Current FPR comes from a **synthetic scenario regression**, not an epidemiological estimate from large real failure logs.  
- Critic→heal still depends on keywords and may miss (FN) cases that truly need a re-run.  
- Even if HITL approves `lower_kraken_confidence`, contamination may still be masked—prefer host filtering and reference DB checks first.  
- After expanding real stderr corpora, re-run `evaluate_self_heal_fpr` and update the numbers in this section.
