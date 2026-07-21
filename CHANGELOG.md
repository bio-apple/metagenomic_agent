# Changelog

## 0.11.0

- Summary-driven pipeline context: Q30 / reads / N50 / CheckM completeness only — never raw sequences in LLM window
- Post-run reproducible export: `workflow/reproducible.nf` · `.smk`, `seeds.json`, `config_snapshot.yaml`
- Extended reproducibility bundle with seed + summary references

## 0.10.0

- Authority-bound RAG (GTDB, NCBI Taxonomy, KEGG, UniProt, CARD): ungrounded taxa blocked
- Evidence chains: abundance / p·q-value / DB IDs / PMIDs on biological claims (`evidence/claims.*`)
- Literature & interpreter constrained to retrieval context; UniProt curated + optional REST

## 0.9.0

- MCP-style sandboxed tool calls (`tools/sandbox.py`) with Docker/Apptainer backends
- Platform/memory/CPU limits; Apple Silicon → amd64 container emulation guidance
- Stronger stderr classification (arch/lib/missing binary) and user-facing heal summaries
- Self-heal actions: switch_to_container, pin_platform_amd64, mock fallback

## 0.8.0

- Router / Tool Specialist / Plan Validator; domain KB; workflow RAG; XAI

## 0.7.0

- PCoA/Spearman/LEfSe-like/ANCOM-like, TF-IDF RAG, PI, contract hard-fail, gLM hook

## 0.6.0 – 0.1.x

- Bio-RAG, contracts, Linux production, LangGraph MVP
