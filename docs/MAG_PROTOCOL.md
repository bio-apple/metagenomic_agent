# MAG construction and functional profiling protocol

Aligned with Banerjee *et al.* 2024 (*STAR Protocols*) and agent implementation (`mag_agent` / `assembly_agent`).

## Steps

1. **QC / host depletion** — fastp (+ Bowtie2/KneadData when host-associated).  
2. **Assembly** — short-read MEGAHIT or metaSPAdes; long-read Flye (`--meta`).  
3. **Binning** — MetaBAT2, MaxBin2, CONCOCT, optional VAMB.  
4. **Refinement** — DAS Tool consensus.  
5. **Quality** — CheckM2 (completeness/contamination) + BUSCO; HQ ≥90%/≤5%, MQ ≥50%/≤10%.  
6. **Taxonomy** — GTDB-Tk on passed bins.  
7. **Function / ARG on MAGs** — Bakta or DIAMOND/eggNOG when configured; Resistance Agent (RGI / AMRFinderPlus) on contigs or MAG FAAs.  
8. **Summary** — `mags/mag_summary.tsv` + `mag_summary.json` (HQ/MQ/LQ counts).

## Agent entry points

```bash
# Enable assembly via query or config
meta-agent run ... -q "MAG recovery from soil shotgun" --mode docker -c config/site.yaml
# pipeline.enable_assembly / bio_reasoning.enable_assembly
```

Large cohorts (≥ `pipeline.auto_mag_min_samples`, default 20) automatically recommend MAG recovery.

## Outputs

| Path | Content |
|------|---------|
| `{sample}/assembly/` | Contigs + checkpoint |
| `{sample}/binning/` | Per-binner dirs + `das_tool/` |
| `mags/mag_summary.*` | Cohort MAG quality table |

See [ARCHITECTURE.md](ARCHITECTURE.md) and [paper/README.md](../paper/README.md).
