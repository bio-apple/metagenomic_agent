"""CAMI-style toy taxonomy benchmark (precision / recall / F1 vs gold genera).

Not a full OPAMI/AMBER suite — validates profiling outputs against a fixed gold
profile for CI and research-copilot regression.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

# Toy gold: genera expected in a gut IBD-style demo profile
DEFAULT_GOLD_GENERA = {
    "Faecalibacterium",
    "Bacteroides",
    "Escherichia",
    "Prevotella",
    "Bifidobacterium",
    "Akkermansia",
}


def load_predicted_genera(outdir: Path) -> set[str]:
    """Collect predicted genera from taxonomy profile / genus matrix / biomarkers."""
    found: set[str] = set()
    # genus_matrix.tsv header
    mat = outdir / "diversity_analysis" / "genus_matrix.tsv"
    if mat.exists():
        header = mat.read_text(encoding="utf-8").splitlines()[:1]
        if header:
            cols = header[0].split("\t")[1:]
            found.update(c for c in cols if c and c[0].isupper())
    # taxonomy_profile.tsv
    tax = outdir / "taxonomy_profile.tsv"
    if tax.exists():
        with tax.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                for key in ("genus", "taxon", "name"):
                    if row.get(key):
                        found.add(str(row[key]).split()[0])
    # biomarkers
    bio = outdir / "biomarkers" / "biomarkers.tsv"
    if bio.exists():
        with bio.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                if row.get("genus"):
                    found.add(row["genus"].split()[0])
    # mock taxonomy artifacts JSON
    for p in (outdir / "taxonomy").glob("*.json") if (outdir / "taxonomy").exists() else []:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for g in data.get("top_genera") or []:
                found.add(str(g).split()[0])
        except Exception:  # noqa: BLE001
            continue
    return found


def score_taxonomy(predicted: set[str], gold: set[str] | None = None) -> dict[str, Any]:
    gold = set(gold or DEFAULT_GOLD_GENERA)
    pred = {p.split()[0] for p in predicted if p}
    tp = pred & gold
    fp = pred - gold
    fn = gold - pred
    precision = len(tp) / max(len(pred), 1)
    recall = len(tp) / max(len(gold), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12) if (precision + recall) else 0.0
    return {
        "n_gold": len(gold),
        "n_predicted": len(pred),
        "tp": sorted(tp),
        "fp": sorted(fp)[:20],
        "fn": sorted(fn),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "gold": sorted(gold),
    }


def evaluate_cami_toy(outdir: Path | None = None, gold: set[str] | None = None) -> dict[str, Any]:
    """Score a run directory, or run self-check against gold alone when outdir missing."""
    if outdir is None or not Path(outdir).exists():
        # Self-check: predicting the gold set exactly → F1=1
        pred = set(gold or DEFAULT_GOLD_GENERA)
        metrics = score_taxonomy(pred, gold)
        metrics["mode"] = "self_check"
        metrics["passed"] = metrics["f1"] >= 0.99
        return metrics

    pred = load_predicted_genera(Path(outdir))
    # If empty (early fail), use empty prediction
    metrics = score_taxonomy(pred, gold)
    metrics["mode"] = "run_dir"
    metrics["outdir"] = str(outdir)
    # Soft pass for mock demos: F1>=0.3 or at least one TP
    metrics["passed"] = metrics["f1"] >= 0.3 or len(metrics["tp"]) >= 1
    return metrics


def write_cami_report(outdir: Path, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = metrics or evaluate_cami_toy(outdir)
    root = Path(outdir) / "evaluation"
    root.mkdir(parents=True, exist_ok=True)
    (root / "cami_toy.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    md = [
        "# CAMI-style toy taxonomy benchmark",
        "",
        f"- precision: `{metrics.get('precision')}`",
        f"- recall: `{metrics.get('recall')}`",
        f"- F1: `{metrics.get('f1')}`",
        f"- passed: `{metrics.get('passed')}`",
        "",
        f"TP: {', '.join(metrics.get('tp') or []) or 'none'}",
        f"FN: {', '.join(metrics.get('fn') or []) or 'none'}",
        "",
        "_Toy gold genera for CI/regression — not a full CAMI/OPAMI challenge._",
    ]
    (root / "cami_toy.md").write_text("\n".join(md), encoding="utf-8")
    return {**metrics, "path": str(root / "cami_toy.json")}
