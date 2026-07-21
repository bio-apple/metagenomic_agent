# Gut shotgun metagenomics — best-practice notes

Consumed by the Supervisor when drafting plans (runtime KB, not end-user docs).

## Typical pipeline

1. QC with fastp; host removal when human gut samples and index are available.  
2. Taxonomy via domain routing (prokaryote → Kraken2/MetaPhlAn; virus → ViWrap/PhaBOX when relevant; long reads → gLM).  
3. Function / AMR via DIAMOND or labeled profiles when requested.  
4. Assembly–binning only for explicit MAG goals.  
5. Differential stats + Evidence Table + XAI before strong biological claims.

## Safety

- Do not invent host genome versions, coordinate systems, or sample groups — escalate to Plan Validator / HITL.  
- Prefer multi-tool consensus for taxonomy when compute allows.  
- Do not assert taxa absent from GTDB/NCBI authority RAG; attach abundance, p/q-value, DB IDs, and PMIDs on biological claims.  
- LLM text must paraphrase retrieval context only — no invented species, pathways, or causal disease claims.  
- Never load raw Fastq/Bam/Fasta sequence content into LLM prompts; use `pipeline_summary` metadata (Q30, reads, N50, CheckM).  
- After analysis, keep `workflow/reproducible.nf|.smk` and `seeds.json` for peer review.
