#!/usr/bin/env bash
# One-click reviewer / CI smoke: install check + unit tests + mock demo pipeline.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUTDIR="${OUTDIR:-$ROOT/results/demo_reproduce}"
PYTHON="${PYTHON:-python3}"

echo "==> [1/4] Python $(${PYTHON} -V 2>&1)"
if ! ${PYTHON} -c "import metagenomic_agent" 2>/dev/null; then
  echo "==> editable install (.[dev])"
  ${PYTHON} -m pip install -e ".[dev]"
fi

echo "==> [2/4] unit tests"
${PYTHON} -m pytest -q

echo "==> [3/4] mock demo pipeline (bundled FASTQ, no reference DBs)"
rm -rf "$OUTDIR"
meta-agent run \
  -i examples/demo_data/fastq \
  --metadata examples/demo_data/metadata.tsv \
  -o "$OUTDIR" \
  --mode mock \
  --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"

echo "==> [4/4] key outputs"
ls -la "$OUTDIR" | head -40
REPORT=""
for cand in final_report.html report.html final_report.md report.md; do
  if [[ -f "$OUTDIR/$cand" ]]; then
    REPORT="$OUTDIR/$cand"
    break
  fi
done
if [[ -z "$REPORT" ]]; then
  echo "ERROR: expected final_report.html (or report.*) under $OUTDIR" >&2
  exit 1
fi

echo
echo "OK — reproduction finished."
echo "  outdir: $OUTDIR"
echo "  open:   $REPORT"
echo "  note:   mock mode is for software reproducibility, not biological truth."
