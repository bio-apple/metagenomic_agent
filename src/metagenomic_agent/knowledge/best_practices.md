# Gut shotgun metagenomics — runtime best practices

Consumed by the Supervisor when drafting plans (not end-user docs).

## Pipeline

1. QC (fastp); host removal when index is available.  
2. Taxonomy via domain routing (prokaryote → Kraken2/MetaPhlAn; virus → ViWrap/PhaBOX when relevant; long reads → gLM).  
3. Function/AMR when requested; assembly–binning only for MAG goals.  
4. Differential stats + evidence chains + XAI before strong claims.  
5. Prefer interactive dashboard figures for user-facing composition/diversity/PCoA/heatmap.

## Safety

- Do not invent host genome versions, coordinate systems, or sample groups — escalate to Plan Validator / HITL.  
- Do not assert taxa absent from GTDB/NCBI authority RAG; attach abundance, p/q, DB IDs, PMIDs.  
- LLM text must paraphrase retrieval context only.  
- Never load raw Fastq/Bam/Fasta into LLM prompts; use `pipeline_summary`.  
- Keep `workflow/reproducible.nf|.smk` and `seeds.json` after analysis.
