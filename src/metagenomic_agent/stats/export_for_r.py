"""Export count/relative tables + R scripts for DESeq2 / MaAsLin2 / ANCOM-BC.

When R + packages are available, optionally run via Rscript; otherwise leave
scripts for the analyst and keep Python *‑like fallbacks.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path
from typing import Any


def export_r_bundle(
    matrix: dict[str, dict[str, float]],
    groups: dict[str, str],
    outdir: Path,
    *,
    try_run: bool = False,
) -> dict[str, Any]:
    """Write feature table, metadata, and R runners under biomarkers/r_export/."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    samples = sorted(matrix)
    taxa = sorted({t for ab in matrix.values() for t in ab})

    # Relative abundance table (MaAsLin2-friendly)
    rel_path = out / "feature_rel.tsv"
    with rel_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["feature"] + samples)
        for t in taxa:
            w.writerow([t] + [f"{matrix[s].get(t, 0.0):.8g}" for s in samples])

    # Pseudo-counts for DESeq2 (scale relative → integer-like)
    count_path = out / "feature_counts.tsv"
    with count_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["feature"] + samples)
        for t in taxa:
            row = []
            for s in samples:
                # scale to ~1e6 library for DESeq2 toy input
                row.append(str(max(0, int(round(matrix[s].get(t, 0.0) * 1_000_000)))))
            w.writerow([t] + row)

    meta_path = out / "sample_metadata.tsv"
    with meta_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["sample_id", "group"])
        for s in samples:
            w.writerow([s, groups.get(s, "unknown")])

    deseq_r = out / "run_deseq2.R"
    deseq_r.write_text(
        """#!/usr/bin/env Rscript
# DESeq2 on pseudo-counts from metagenomic-agent export
suppressPackageStartupMessages({
  library(DESeq2)
})
counts <- as.matrix(read.delim("feature_counts.tsv", row.names=1, check.names=FALSE))
meta <- read.delim("sample_metadata.tsv", row.names=1, stringsAsFactors=TRUE)
meta <- meta[colnames(counts), , drop=FALSE]
dds <- DESeqDataSetFromMatrix(countData=counts, colData=meta, design=~group)
dds <- DESeq(dds)
res <- results(dds)
write.csv(as.data.frame(res), "deseq2_results.csv")
message("Wrote deseq2_results.csv")
""",
        encoding="utf-8",
    )

    maaslin_r = out / "run_maaslin3.R"
    maaslin_r.write_text(
        """#!/usr/bin/env Rscript
# MaAsLin3 (falls back to Maaslin2 API if Maaslin3 unavailable)
suppressPackageStartupMessages({
  if (requireNamespace("Maaslin3", quietly=TRUE)) {
    library(Maaslin3)
  } else {
    library(Maaslin2)
  }
})
df <- read.delim("feature_rel.tsv", row.names=1, check.names=FALSE)
meta <- read.delim("sample_metadata.tsv", row.names=1, stringsAsFactors=TRUE)
feat <- as.data.frame(t(df))
meta <- meta[rownames(feat), , drop=FALSE]
if (exists("Maaslin3", mode="function") || "Maaslin3" %in% loadedNamespaces()) {
  Maaslin3(input_data=feat, input_metadata=meta, output="maaslin3_out",
           fixed_effects=c("group"), normalization="NONE", transform="LOG", standardize=FALSE)
} else {
  Maaslin2(input_data=feat, input_metadata=meta, output="maaslin3_out",
           fixed_effects=c("group"), normalization="NONE", transform="LOG", standardize=FALSE)
}
message("Wrote maaslin3_out/")
""",
        encoding="utf-8",
    )
    # Keep legacy filename for older docs
    (out / "run_maaslin2.R").write_text(maaslin_r.read_text(encoding="utf-8"), encoding="utf-8")

    ancom_r = out / "run_ancombc2.R"
    ancom_r.write_text(
        """#!/usr/bin/env Rscript
# ANCOM-BC2 (ANCOMBC::ancombc2) on pseudo-counts
suppressPackageStartupMessages({
  library(ANCOMBC)
  library(phyloseq)
})
counts <- as.matrix(read.delim("feature_counts.tsv", row.names=1, check.names=FALSE))
meta <- read.delim("sample_metadata.tsv", row.names=1, stringsAsFactors=TRUE)
meta <- meta[colnames(counts), , drop=FALSE]
OTU <- otu_table(counts, taxa_are_rows=TRUE)
SD <- sample_data(meta)
ps <- phyloseq(OTU, SD)
if ("ancombc2" %in% getNamespaceExports("ANCOMBC")) {
  out <- ancombc2(data=ps, assay_name="counts", tax_level=NULL, fix_formula="group",
                  p_adj_method="BH", group="group", global=TRUE)
  write.csv(as.data.frame(out$res), "ancombc2_results.csv")
} else {
  out <- ancombc(phyloseq=ps, formula="group", p_adj_method="BH", zero_cut=0.9, lib_cut=0,
                 group="group", struc_zero=FALSE, neg_lb=FALSE, tol=1e-5, max_iter=100,
                 conserve=TRUE, alpha=0.05, global=TRUE)
  write.csv(out$res$beta, "ancombc2_results.csv")
}
message("Wrote ancombc2_results.csv")
""",
        encoding="utf-8",
    )
    (out / "run_ancombc.R").write_text(ancom_r.read_text(encoding="utf-8"), encoding="utf-8")

    aldex_r = out / "run_aldex2.R"
    aldex_r.write_text(
        """#!/usr/bin/env Rscript
# ALDEx2 on pseudo-counts
suppressPackageStartupMessages({
  library(ALDEx2)
})
counts <- as.matrix(read.delim("feature_counts.tsv", row.names=1, check.names=FALSE))
meta <- read.delim("sample_metadata.tsv", row.names=1, stringsAsFactors=TRUE)
meta <- meta[colnames(counts), , drop=FALSE]
conds <- as.character(meta$group)
x <- aldex.clr(counts, conds, mc.samples=128, denom="all", verbose=FALSE)
tt <- aldex.ttest(x)
effect <- aldex.effect(x)
write.csv(cbind(tt, effect), "aldex2_results.csv")
message("Wrote aldex2_results.csv")
""",
        encoding="utf-8",
    )

    lmer_r = out / "run_lmer.R"
    lmer_r.write_text(
        """#!/usr/bin/env Rscript
# Mixed model association (lme4) — requires subject column in sample_metadata.tsv when available
suppressPackageStartupMessages({
  library(lme4)
})
rel <- read.delim("feature_rel.tsv", row.names=1, check.names=FALSE)
meta <- read.delim("sample_metadata.tsv", row.names=1, stringsAsFactors=TRUE)
feat <- as.data.frame(t(rel))
meta <- meta[rownames(feat), , drop=FALSE]
# Example: first feature ~ group + (1|subject) if subject present
taxon <- colnames(feat)[1]
df <- data.frame(y=feat[[taxon]], group=meta$group, subject=if ("subject" %in% names(meta)) meta$subject else rownames(meta))
if (length(unique(df$subject)) > 1 && length(unique(df$group)) > 1) {
  fit <- lmer(y ~ group + (1|subject), data=df)
  write.csv(as.data.frame(coef(summary(fit))), "lmer_example.csv")
} else {
  fit <- lm(y ~ group, data=df)
  write.csv(as.data.frame(coef(summary(fit))), "lmer_example.csv")
}
message("Wrote lmer_example.csv")
""",
        encoding="utf-8",
    )

    readme = out / "README.md"
    readme.write_text(
        "# R differential abundance export\n\n"
        "Generated by metagenomic-agent Statistical Reasoning for journal-grade methods.\n\n"
        "```bash\n"
        "cd biomarkers/r_export\n"
        "Rscript run_deseq2.R      # Bioconductor DESeq2\n"
        "Rscript run_maaslin3.R    # MaAsLin3 (or Maaslin2 fallback)\n"
        "Rscript run_ancombc2.R    # ANCOM-BC2 / ANCOMBC\n"
        "Rscript run_aldex2.R      # ALDEx2\n"
        "Rscript run_lmer.R        # mixed model (lme4) example\n"
        "```\n"
        "Pseudo-counts are scaled from relative abundances — prefer true counts when available.\n"
        "Method choice should follow `diversity_analysis/abundance_diagnostics.json`.\n",
        encoding="utf-8",
    )

    result: dict[str, Any] = {
        "feature_rel": str(rel_path),
        "feature_counts": str(count_path),
        "metadata": str(meta_path),
        "run_deseq2": str(deseq_r),
        "run_maaslin3": str(maaslin_r),
        "run_maaslin2": str(out / "run_maaslin2.R"),
        "run_ancombc2": str(ancom_r),
        "run_ancombc": str(out / "run_ancombc.R"),
        "run_aldex2": str(aldex_r),
        "run_lmer": str(lmer_r),
        "readme": str(readme),
        "r_available": bool(shutil.which("Rscript")),
        "executed": [],
    }

    if try_run and result["r_available"]:
        for script in (deseq_r, maaslin_r, ancom_r, aldex_r, lmer_r):
            try:
                proc = subprocess.run(
                    ["Rscript", script.name],
                    cwd=str(out),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                result["executed"].append(
                    {
                        "script": script.name,
                        "returncode": proc.returncode,
                        "stderr_tail": (proc.stderr or "")[-500:],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                result["executed"].append({"script": script.name, "error": str(exc)})

    return result
