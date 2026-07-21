# Methods note (v0.7.x)

> 落地对照：[PROPOSAL_2026_IMPL.md](PROPOSAL_2026_IMPL.md)

## System

`parse → supervisor → export_dag → contract_check → HITL → swarm → validate → quality_scores → self-heal* → critic → literature → pi_review* → visualization → report`

## Analytical methods (as implemented)

| Area | Method |
|------|--------|
| Alpha / beta | Shannon; Bray–Curtis |
| Differential | Mann–Whitney U + BH-FDR (default); optional LEfSe-like (Cohen's d proxy); CLR+MWU (ANCOM-like) |
| Ordination | Classical MDS (PCoA) on Bray–Curtis |
| Networks | Spearman co-occurrence |
| Knowledge | Curated bio-DB RAG + optional TF-IDF semantic mode; Evidence Table |
| gLM | Mock / weights placeholder / external `glm_inference_cmd` |

## Limitations

- LEfSe-like / ANCOM-like are **Python approximations**, not official LEfSe/ANCOM-BC.
- Bio-RAG curated index is compact until full DB dumps are mounted.
- Manuscript drafts require expert editing.
