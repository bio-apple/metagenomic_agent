# Gut shotgun metagenomics — best-practice notes (MVP knowledge base)

## Typical pipeline
1. Quality control with fastp (adapter trim, Q20, length >= 36, optional dedup).
2. Host DNA removal with Bowtie2 against HG38 (or Kneaddata) for human gut samples.
3. Taxonomic profiling: Kraken2+Bracken and/or MetaPhlAn4; prefer multi-tool consensus when compute allows.
4. Functional profiling: HUMAnN4 when pathway abundance is required; otherwise DIAMOND vs UniRef/nr as a lighter alternative.
5. Assembly & binning (MEGAHIT/metaSPAdes → MetaBAT2/MaxBin2 → CheckM2/GTDB-Tk) only when MAG recovery is an explicit goal and depth is sufficient.

## Decision heuristics
- Illumina PE ~150 bp gut samples → default: fastp → host filter → Kraken2+MetaPhlAn → optional DIAMOND.
- If host fraction > 80% after filtering, warn and consider deeper host removal or sample QC failure.
- Skip assembly by default for profiling-only requests; ask human confirmation when depth is unknown.
- Long reads (ONT/PacBio) → route to long-read taxonomy tools / genomic LM stubs when available.

## Validation
- Technical: read retention after QC, non-empty taxonomy tables, CheckM completeness for bins.
- Biological (gut): expect Bacteroides / Faecalibacterium / Prevotella / Bifidobacterium among top genera when community is gut-like.
