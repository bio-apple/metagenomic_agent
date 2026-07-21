# Gut shotgun metagenomics — best-practice notes

Used by the Supervisor Agent when drafting analysis plans.

## Typical pipeline

1. QC with fastp (adapters, Q20, length ≥ 36, optional dedup).
2. Host removal (Bowtie2/Kneaddata vs HG38) for human gut samples.
3. Taxonomy: Kraken2+Bracken and/or MetaPhlAn; long reads → gLM when configured.
4. Function: HUMAnN when pathways needed; else DIAMOND vs UniRef/nr.
5. Assembly/binning only when MAG recovery is an explicit goal and depth is sufficient.

## Decision heuristics

- Illumina PE ~150 bp gut → fastp → host filter → Kraken2±MetaPhlAn → optional DIAMOND.
- Low memory → prefer Kraken2; high accuracy / small cohort → MetaPhlAn.
- Host fraction > 80% after filtering → warn / strengthen host removal.
- Skip assembly for profiling-only queries unless user confirms.
- Long reads (≥5000 bp) → microCafe / MicroRAG routing.

## Validation

- Technical: read retention, non-empty taxonomy, CheckM for bins.
- Biological (gut): expect Bacteroides / Faecalibacterium / Prevotella / Bifidobacterium among top genera when community is gut-like.
- Evidence: link differential taxa to curated PMIDs / online literature before strong claims.
