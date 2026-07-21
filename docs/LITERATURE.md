# Literature-informed design

Metagenomic Agent incorporates methods guidance from the curated corpus under [`paper/`](../paper/README.md) (local PDFs optional; DOIs cited in the Application Note).

## Mapping

| Capability in software | Primary literature driver |
|------------------------|---------------------------|
| Fecal DIAMOND functional parameters | Treiber *et al.* 2020 (BMC Biol.) |
| AMRFinderPlus + virulence catalog | Feldgarden *et al.* 2021 (*Sci Rep*) |
| DIAMOND + MEGAN-style binning | Bağcı *et al.* 2021 (*Curr Protoc*) |
| Kraken2/Bracken protocols | Lu *et al.* 2022 (Kraken suite) |
| Skin / mycobiome / air / wastewater niches | Shen 2023; Yan 2024; Giolai 2024; + existing SOPs |
| Viral discovery multi-tool + CheckV | Zeng 2024 ELGV; Wu *et al.* 2024 virus benchmark |
| Clinical respiratory research SOP | Clinical mNGS validation 2024 (*Nat Commun*) |
| MAG build → QC → function / ARG | Banerjee *et al.* 2024 (*STAR Protocols*) |

## Honest limits

- Clinical respiratory SOP is for **research orchestration**, not a certified diagnostic assay.  
- Virus tool “benchmark” in `evaluation/` is a **regression harness** on toy scenarios, not a reproduction of Wu *et al.*’s multi-biome study.  
- MEGAN integration is **table-level LCA/functional summaries** (MEGAN-lite), not the full MEGAN GUI.
